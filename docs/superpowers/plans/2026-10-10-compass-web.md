# Compass web app and demo system: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (the user chose Native execution for this
> project). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A mobile-first React app on the live Compass API, a Staff Pulse, and a stage + table demo system that runs
the full story reliably and persuasively.

**Architecture:** Static Vite/React/TS app in `web/`, deployed to S3 + CloudFront (`CompassWeb` CDK stack), calling
the existing API with demo bearer tokens. One story script drives both the stage presenter (`/present`, iframe of the
real app + evidence rail) and table tours (`/tour`, coach bar on sandbox sessions). A transport layer can switch from
live HTTP to offline replay.

**Tech stack:** React 19, TypeScript 5, Vite 7, React Router 7, TanStack Query 5, Tailwind CSS 4, motion 12,
@phosphor-icons/react 2, Fontsource (Geist, Instrument Serif), openapi-typescript, qrcode, Vitest + Testing Library +
MSW, Playwright. Backend additions in Python (FastAPI/psycopg), deployed with the existing `scripts/deploy.py`.

**Spec:** `docs/superpowers/specs/2026-10-10-compass-web-design.md` (read it with this plan; section numbers below
refer to it).

**How detailed this plan is:** infrastructure, backend changes, the demo engine and tests are written out as code.
Screens are specified by their spec section, the data they use and an acceptance check, rather than pre-written
JSX. The author executes the plan natively, so writing every component twice would cost hours on event night with
nothing gained.

## Global constraints

- Node 22, npm. All web code lives in `web/`; nothing outside `compass-backend/` is touched (not `ruhack/compass`,
  not `ruhack/compass-chat`).
- API base comes from `VITE_API_BASE` (default `https://d2fap8zqnl1gn5.cloudfront.net`).
- Body text ≥ 16 px on phones; touch targets ≥ 44×44; contrast per spec §5.1; `prefers-reduced-motion` respected.
- No emoji as icons. Phosphor regular only (fill for the active tab).
- Every synthetic item shows its badge (`synthetic: true` → "Sample"); mocks say "(demo)"; nothing claims real
  outcomes.
- Push permission is requested only from the "Turn on reminders" button.
- The stage Reset is the only UI that calls `POST /demo/reset`; table tours never call it.
- Commit after every task with the attribution trailer. Never commit `.env`, tokens or AWS credentials.

## Review focus

1. **Two judges tour Andre at the same time** → each sees their own state. Test: Task 2 `test_sandbox_isolation`.
2. **Network drops mid-story** → the story continues on replay with a visible badge, and no write is pretended. Test:
   Task 13 Playwright `offline story` with routes blocked after chapter 2.
3. **Crisis text typed into any free-text field** (focus words, Ask, win) → crisis screen, nothing echoed. Test:
   Task 6 and Task 9 component tests with `me_focus_crisis.json`, `win_crisis.json`, and the Ask crisis response.
4. **Clock moves (skip/jump)** → every student view refetches; no stale "Tue 12:30 upcoming" after the follow-up.
   Test: Task 4 `clock change invalidates student queries`.
5. **Double tap on "I'm in" or follow-up submit** → exactly one commitment / one feedback. Test: Task 7 and Task 8
   component tests assert one request while pending.

---

## Task 1: Backend encoding fixes

**Files:** Modify `config/barriers.yaml` (and any YAML with mojibake), `scripts/record_fixtures.py` /
`scripts/build_fixtures.py` (write UTF-8 explicitly), `fixtures/**.json` (re-record). Create `tests/test_encoding.py`.

- [ ] **Step 1: Failing test**

```python
# tests/test_encoding.py
import json
from pathlib import Path

BAD = ("Ã", "â€", "Â")
ROOT = Path(__file__).resolve().parents[1]


def _files():
    yield from (ROOT / "fixtures").rglob("*.json")
    yield from (ROOT / "config").glob("*.yaml")
    yield from (ROOT / "seed").rglob("*.yaml")


def test_no_mojibake_in_fixtures_or_config():
    offenders = []
    for f in _files():
        text = f.read_text(encoding="utf-8")
        if f.suffix == ".json":
            text = json.dumps(json.loads(text), ensure_ascii=False)
        if any(b in text for b in BAD):
            offenders.append(str(f.relative_to(ROOT)))
    assert offenders == []
```

- [ ] **Step 2:** `../compass/.venv/Scripts/python -m pytest tests/test_encoding.py -q` → FAIL listing
  `config/barriers.yaml`, `fixtures/*/me_card.json`, `fixtures/*/win_crisis.json`, `fixtures/_shared/invite.json`, …
- [ ] **Step 3:** Repair text with a one-off `s.encode("cp1252").decode("utf-8")` pass on offending strings (YAML
  edited by hand where few); make the fixture writers use `open(..., "w", encoding="utf-8")` and
  `json.dump(..., ensure_ascii=False)`; re-run `python -m scripts.build_fixtures` (or re-record against production).
- [ ] **Step 4:** Test passes; full suite `pytest -q` still green (~260 tests).
- [ ] **Step 5:** Commit `fix(encoding): repair double-encoded Spanish labels and fixtures; guard test`.

## Task 2: Sandbox sessions

**Files:** Create `db/migrations/004_sandbox.sql`, `tests/test_sandbox.py`. Modify `app/auth.py`,
`app/services/demo.py`, `app/models/demo.py` (request field), `app/routes/demo.py`, `app/workers.py` (cleanup),
`contract/openapi.json` + `contract/CHANGELOG.md` (v1.2.0, additive).

**Interfaces:**
- Produces: `POST /demo/session {"persona": str, "sandbox": bool = false, "start": datetime | null}` →
  `SessionResponse` (unchanged shape; `student_id` is the clone id). `SessionCtx.sandbox: bool`.

- [ ] **Step 1: Migration**

```sql
-- db/migrations/004_sandbox.sql
ALTER TABLE students ADD COLUMN IF NOT EXISTS sandbox boolean NOT NULL DEFAULT false;
ALTER TABLE students ADD COLUMN IF NOT EXISTS sandbox_created timestamptz;
CREATE INDEX IF NOT EXISTS students_sandbox_idx ON students (sandbox) WHERE sandbox;

-- Staff never count sandbox clones: redefine the single population entry point.
-- (Body copied from 003 with one added predicate: AND NOT s.sandbox.)
```

  Copy `staff_population` from `003_staff_role_and_functions.sql` verbatim into 004 as `CREATE OR REPLACE` and add
  `AND NOT s.sandbox` to its `WHERE`. If `staff_gaps` counts students without `staff_population`, add the same predicate
  there.

- [ ] **Step 2: Failing tests**

```python
# tests/test_sandbox.py
from fastapi.testclient import TestClient


def _session(client, persona, sandbox):
    r = client.post("/demo/session", json={"persona": persona, "sandbox": sandbox})
    assert r.status_code == 200
    return r.json()


def test_sandbox_gets_clone_id(client: TestClient):
    s = _session(client, "andre", True)
    assert s["student_id"].startswith("DEMO-ANDRE~")


def test_sandbox_isolation(client: TestClient):
    a = _session(client, "andre", True)
    b = _session(client, "andre", True)
    ha = {"Authorization": f"Bearer {a['token']}"}
    hb = {"Authorization": f"Bearer {b['token']}"}
    client.post("/me/focus", json={"dimension": "social", "barriers": ["no_time", "dont_know_anyone"]}, headers=ha)
    assert client.get("/me/map", headers=ha).json()["profile"]["focus"] == "social"
    assert client.get("/me/map", headers=hb).json()["profile"]["focus"] is None
    base = _session(client, "andre", False)
    assert client.get("/me/map", headers={"Authorization": f"Bearer {base['token']}"}).json()["profile"]["focus"] is None


def test_sandbox_story_matches_base(client: TestClient):
    s = _session(client, "andre", True)
    h = {"Authorization": f"Bearer {s['token']}"}
    client.post("/me/focus", json={"dimension": "social", "barriers": ["no_time", "dont_know_anyone"]}, headers=h)
    nxt = client.get("/me/next", headers=h).json()
    assert nxt["pick"]["item"]["id"] == "pin-andre-lunch-2026-10-13"


def test_staff_excludes_sandbox(client: TestClient, staff_headers):
    before = client.get("/staff/funnel", headers=staff_headers).json()
    _session(client, "andre", True)
    after = client.get("/staff/funnel", headers=staff_headers).json()
    assert before["rows"] == after["rows"]


def test_reset_removes_sandboxes(client: TestClient, db):
    _session(client, "andre", True)
    client.post("/demo/reset")
    assert db.execute("SELECT count(*) AS n FROM students WHERE sandbox").fetchone()["n"] == 0
```

  (Use the existing `client`/`db` fixtures in `tests/conftest.py`; add `staff_headers` there if missing.)

- [ ] **Step 3: Run** `pytest tests/test_sandbox.py -q` → FAIL (`sandbox` field unknown / id not cloned).
- [ ] **Step 4: Implement**

```python
# app/auth.py (additions)
SANDBOX_PREFIX = "sb"

@dataclass(frozen=True)
class SessionCtx:
    token: str
    persona: str
    sid: str

    @property
    def sandbox(self) -> bool:
        return self.sid.startswith(SANDBOX_PREFIX)

    @property
    def student_id(self) -> str | None:
        base = PERSONA_STUDENT.get(self.persona)
        return f"{base}~{self.sid}" if base and self.sandbox else base


def issue(persona: str, sandbox: bool = False) -> SessionCtx:
    sid = (SANDBOX_PREFIX if sandbox else "") + secrets.token_urlsafe(9).replace("sb", "s_")  # base sids never start with "sb"
    payload = f"v1.{persona}.{sid}"
    return SessionCtx(token=f"{payload}.{_sig(payload)}", persona=persona, sid=sid)
```

  Note: `token_urlsafe` can start with "sb"; the `.replace` guard keeps non-sandbox sids from ever starting with
  the prefix. Tokens contain `.` separators only between parts; urlsafe base64 has no `.`.

```python
# app/services/demo.py (called inside start_session, before the demo_sessions insert, when ctx.sandbox)
from psycopg import sql

_COLS: dict[str, list[str]] = {}


def _cols(c, table: str) -> list[str]:
    if table not in _COLS:
        rows = c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s "
                         "AND table_schema = current_schema() ORDER BY ordinal_position", (table,)).fetchall()
        _COLS[table] = [r["column_name"] for r in rows]
    return _COLS[table]


def _copy(c, table: str, key: str, base_id: str, clone_id: str, skip: tuple[str, ...] = ("id",),
          override: dict[str, object] | None = None) -> None:
    """INSERT INTO table (cols) SELECT cols FROM table WHERE key = base_id, with key := clone_id."""
    override = {key: clone_id, **(override or {})}
    cols = [col for col in _cols(c, table) if col not in skip or col in override]
    select = [sql.Placeholder() if col in override else sql.Identifier(col) for col in cols]
    params = [override[col] for col in cols if col in override] + [base_id]
    c.execute(sql.SQL("INSERT INTO {t} ({cols}) SELECT {sel} FROM {t} WHERE {k} = %s").format(
        t=sql.Identifier(table), cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
        sel=sql.SQL(", ").join(select), k=sql.Identifier(key)), params)


def clone_persona(c, base_id: str, clone_id: str, now) -> None:
    _copy(c, "students", "id", base_id, clone_id, skip=(), override={"sandbox": True, "sandbox_created": now})
    for table in ("profiles", "consents", "student_memory"):
        _copy(c, table, "student_id", base_id, clone_id)
    takes = c.execute("SELECT id, take_no, taken_on, source, total FROM inventory_takes WHERE student_id = %s",
                      (base_id,)).fetchall()
    for t in takes:  # dimension_scores hang off take ids, so map old -> new per take
        new_id = c.execute("INSERT INTO inventory_takes (student_id, take_no, taken_on, source, total) "
                           "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                           (clone_id, t["take_no"], t["taken_on"], t["source"], t["total"])).fetchone()["id"]
        c.execute("INSERT INTO dimension_scores (take_id, dimension, score) "
                  "SELECT %s, dimension, score FROM dimension_scores WHERE take_id = %s", (new_id, t["id"]))
```

  `skip=("id",)` drops serial ids so new rows get fresh ones (profiles is keyed by `student_id`, so it has no `id`;
  the helper skips only columns that exist). Future takes (the Oct 26 retake) are cloned too; the clock filters them
  exactly as for the base persona. If a later migration added `inventory_takes` columns, extend the explicit list.

  In `routes/demo.py`, accept `sandbox` in the request model and call `issue(persona, sandbox)`. In
  `workers.py` dispatcher loop, every ~10 minutes: `DELETE FROM students WHERE sandbox AND sandbox_created < now() - interval '6 hours'`.

- [ ] **Step 5:** `pytest -q` green. Update `contract/openapi.json` via `python -m scripts.export_openapi`, add
  CHANGELOG v1.2.0 ("additive: `sandbox` on /demo/session; `X-Compass-Trace` header").
- [ ] **Step 6:** Commit `feat(demo): sandbox sessions clone a persona per tour; staff and reset exclude them`.

## Task 3: Trace header, Priya wording, backend deploy

**Files:** Modify `app/services/student.py` (`set_focus`, `get_next`, `ask`), `app/services/social.py` (`post_win`),
`app/engine/rank.py` (return counts), `app/main.py` (CORS `expose_headers` += `X-Compass-Trace`),
`app/llm/templates.py` (root-cause line), `app/services/prewarm.py` (Priya). Create `tests/test_trace.py`.

**Interfaces:**
- Produces header `X-Compass-Trace: safety=lexicon;safety_ms=0.4;candidates=193;passed=41;rank_ms=3.1;wording=ai`.
  Keys are optional per route. Parsed by the web app's `parseTrace(h: string): Record<string,string>`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_trace.py
def _h(client, persona="andre"):
    t = client.post("/demo/session", json={"persona": persona, "sandbox": True}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def _trace(r):
    return dict(p.split("=", 1) for p in r.headers["X-Compass-Trace"].split(";") if p)


def test_next_has_rank_trace(client):
    h = _h(client)
    client.post("/me/focus", json={"dimension": "social", "barriers": ["no_time"]}, headers=h)
    tr = _trace(client.get("/me/next", headers=h))
    assert int(tr["candidates"]) >= int(tr["passed"]) > 0
    assert tr["wording"] in {"ai", "template", "cache"}


def test_focus_crisis_trace_says_lexicon(client):
    h = _h(client)
    r = client.post("/me/focus", json={"dimension": "emotional", "barriers": [], "text": "i want to kill myself"}, headers=h)
    assert r.json()["kind"] == "crisis"
    assert _trace(r)["safety"] == "lexicon"


def test_trace_exposed_to_browsers(client):
    r = client.options("/me/next", headers={"Origin": "https://x.example", "Access-Control-Request-Method": "GET"})
    assert r.status_code in (200, 204)
    r2 = client.get("/health", headers={"Origin": "https://x.example"})
    assert "X-Compass-Trace" in r2.headers.get("access-control-expose-headers", "")
```

  (`FocusRequest.text` is the free-text field, max 500 chars, in `app/models/student.py`.)

- [ ] **Step 2:** Run → FAIL (no header).
- [ ] **Step 3: Implement.** A tiny helper in `app/routes/_serve.py`:

```python
def set_trace(response, **kv) -> None:
    parts = [f"{k}={v}" for k, v in kv.items() if v is not None]
    if parts:
        response.headers["X-Compass-Trace"] = ";".join(parts)
```

  `rank()` returns its counts (`candidates`, `passed`) and elapsed ms on the result object; services pass them plus
  the safety verdict's stage/ms and the wording source up to the route, which calls `set_trace`. Values are numbers
  or enum words only (no free text). Add `"X-Compass-Trace"` to `expose_headers`.
  Priya: add a root-cause template for `barrier=coursework` + tutoring items ("Free drop-in tutoring at {venue}, so
  coursework stops eating your nights.") and include Priya's focus in `prewarm.py`'s scripted inputs.
- [ ] **Step 4:** `pytest -q` green; `python -m scripts.try_engine priya` shows the new why.
- [ ] **Step 5:** Deploy: `python -m scripts.deploy --mode live` (migration 004 applies via the init task:
  `python -m scripts.deploy --task migrate`), then `python -m scripts.smoke https://d2fap8zqnl1gn5.cloudfront.net --reset --quick`
  → `RESULT: ALL PASS`. Spot-check: `curl -si .../meta/barriers` shows "lo mío"; a sandbox session works on prod.
- [ ] **Step 6:** Commit `feat(api): X-Compass-Trace header, Priya root-cause wording; contract v1.2.0`.

## Task 4: Web scaffold, transport, session, clock

**Files:** Create `web/` (Vite React-TS template), `web/src/api/{transport,client,inspector,types}.ts`,
`web/src/session/{session,clock}.ts`, `web/src/app/{providers,routes}.tsx`, `web/src/styles/tokens.css`,
`web/src/i18n/{en,es,useT}.ts`, `web/vitest.config.ts`, `web/tests/unit/transport.test.ts`,
`web/tests/unit/clock.test.ts`, `web/tests/setup.ts` (MSW with backend fixtures).

**Interfaces:**
- Produces:
  - `type CallLog = { id: string; method: string; path: string; ms: number; status: number; fallback: "fixture"|"template"|null; trace: Record<string,string>; requestId?: string; source: "live"|"replay" }`
  - `inspector.on(fn: (e: InspectorEvent) => void): () => void`, `inspector.emit(e)`; `InspectorEvent = {type:"call", call: CallLog} | {type:"signal", name: Signal, data?: unknown}`
  - `transport.request<T>(method, path, body?) : Promise<{ data: T; call: CallLog }>`; `setTransport(kind: "live"|"replay")`
  - `api.*` typed wrappers: `session(persona, sandbox)`, `personas()`, `map()`, `focus(body)`, `next()`, `decline(recId, reason)`, `commit(recId)`, `invite(token)`, `acceptInvite(token)`, `followup(id, body)`, `inbox()`, `memory()`, `deleteMemory(id)`, `deleteAllMemory()`, `forgetMe()`, `pulse()`, `postWin(text, dimension)`, `sameHere(id)`, `ask(q)`, `card()`, `barriers()`, `skipAhead(to)`, `setClock(now)`, `reset()`, `forceTemplates(on)`, `vapidKey()`, `subscribePush(sub)`, `staff.{funnel,gaps,weekly,dips,retakes,ask}(filters)`
  - `useSession(): { token, persona, role, sandbox, start(persona, sandbox), join(token), clear() }` (token in `sessionStorage`, key `compass.session`)
  - `useClock(): { now: string; set(now: string): void }`; any response with a different `now` calls `set`, which invalidates `['map','next','inbox','memory','pulse','card']`.

- [ ] **Step 1: Scaffold**

```bash
cd web 2>/dev/null || (npm create vite@latest web -- --template react-ts && cd web)
npm i react-router@7 @tanstack/react-query@5 motion @phosphor-icons/react @fontsource-variable/geist @fontsource/instrument-serif qrcode
npm i -D tailwindcss@4 @tailwindcss/vite openapi-typescript vitest @vitest/coverage-v8 jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom msw @types/qrcode @playwright/test
npx openapi-typescript ../contract/openapi.json -o src/api/schema.d.ts
```

  (If `@fontsource-variable/geist` is unavailable, use `@fontsource-variable/figtree` and note it in DECISIONS.)

- [ ] **Step 2: Failing transport tests**

```ts
// web/tests/unit/transport.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { http, HttpResponse, delay } from "msw";
import { server } from "../setup";
import { transport, setTransport } from "../../src/api/transport";
import { inspector } from "../../src/api/inspector";

const BASE = "https://api.test";

describe("live transport", () => {
  beforeEach(() => setTransport("live", { base: BASE, token: () => "tok" }));

  it("sends bearer token and reports fallback + trace", async () => {
    server.use(http.get(`${BASE}/me/next`, ({ request }) => {
      expect(request.headers.get("authorization")).toBe("Bearer tok");
      return HttpResponse.json({ now: "2026-10-12T09:00:00-04:00" }, {
        headers: { "X-Compass-Fallback": "fixture", "X-Compass-Trace": "candidates=193;passed=41" } });
    }));
    const seen: unknown[] = [];
    const off = inspector.on(e => seen.push(e));
    const { call } = await transport.request("GET", "/me/next");
    off();
    expect(call.fallback).toBe("fixture");
    expect(call.trace).toEqual({ candidates: "193", passed: "41" });
    expect(seen).toHaveLength(1);
  });

  it("times out after 8s and retries GET once", async () => {
    vi.useFakeTimers();
    let hits = 0;
    server.use(http.get(`${BASE}/me/map`, async () => { hits++; await delay("infinite"); return HttpResponse.json({}); }));
    const p = transport.request("GET", "/me/map");
    await vi.advanceTimersByTimeAsync(16_100);
    await expect(p).rejects.toThrow(/timed out/i);
    expect(hits).toBe(2);
    vi.useRealTimers();
  });

  it("never retries POST", async () => {
    let hits = 0;
    server.use(http.post(`${BASE}/commitments`, () => { hits++; return new HttpResponse(null, { status: 502 }); }));
    await expect(transport.request("POST", "/commitments", { rec_id: 1 })).rejects.toThrow();
    expect(hits).toBe(1);
  });
});
```

- [ ] **Step 3:** `npx vitest run` → FAIL (modules missing).
- [ ] **Step 4: Implement** `transport.ts`:

```ts
// web/src/api/transport.ts
import { inspector, type CallLog } from "./inspector";
import { replayRequest } from "../demo/replay/replay";

type Opts = { base: string; token: () => string | null };
let kind: "live" | "replay" = "live";
let opts: Opts = { base: import.meta.env.VITE_API_BASE ?? "https://d2fap8zqnl1gn5.cloudfront.net", token: () => null };
let consecutiveFailures = 0;

export function setTransport(k: "live" | "replay", o?: Partial<Opts>) { kind = k; opts = { ...opts, ...o }; consecutiveFailures = 0; }
export const transportKind = () => kind;

export class ApiError extends Error { constructor(msg: string, public status: number, public body?: unknown) { super(msg); } }

export function parseTrace(h: string | null): Record<string, string> {
  if (!h) return {};
  return Object.fromEntries(h.split(";").filter(Boolean).map(p => { const i = p.indexOf("="); return [p.slice(0, i), p.slice(i + 1)]; }));
}

async function once<T>(method: string, path: string, body?: unknown): Promise<{ data: T; call: CallLog }> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 8000);
  const t0 = performance.now();
  try {
    const token = opts.token();
    const r = await fetch(opts.base + path, {
      method, signal: ctl.signal,
      headers: { ...(body !== undefined ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const data = r.status === 204 ? (undefined as T) : await r.json().catch(() => undefined);
    const call: CallLog = {
      id: crypto.randomUUID(), method, path, ms: Math.round(performance.now() - t0), status: r.status,
      fallback: (r.headers.get("X-Compass-Fallback") as CallLog["fallback"]) ?? null,
      trace: parseTrace(r.headers.get("X-Compass-Trace")), requestId: r.headers.get("X-Request-Id") ?? undefined, source: "live",
    };
    inspector.emit({ type: "call", call });
    if (!r.ok) throw new ApiError(messageFor(r.status, data), r.status, data);
    return { data: data as T, call };
  } catch (e) {
    if ((e as Error).name === "AbortError") throw new ApiError("Request timed out", 0);
    throw e;
  } finally { clearTimeout(timer); }
}

function messageFor(status: number, body: unknown): string {
  const d = (body as { detail?: { message?: string } | string })?.detail;
  if (typeof d === "string") return d;
  if (d?.message) return d.message;
  return status >= 500 ? "Compass is having trouble right now. Try again." : "That didn't go through. Try again.";
}

export const transport = {
  async request<T>(method: string, path: string, body?: unknown): Promise<{ data: T; call: CallLog }> {
    if (kind === "replay") return replayRequest<T>(method, path, body);
    try {
      const res = await once<T>(method, path, body);
      consecutiveFailures = 0;
      return res;
    } catch (e) {
      const status = e instanceof ApiError ? e.status : 0;
      if (status === 0 || status >= 500) consecutiveFailures++;
      if (method === "GET" && (status === 0 || status >= 500)) {
        try { const res = await once<T>(method, path, body); consecutiveFailures = 0; return res; } catch (e2) { consecutiveFailures++; throw e2; }
      }
      throw e;
    }
  },
  failures: () => consecutiveFailures,
};
```

  `inspector.ts` is a 20-line typed emitter (Set of listeners). `replay.ts` starts as a stub that throws
  "Replay not loaded" (filled in Task 13). `clock.ts` is a tiny store (`useSyncExternalStore`) holding `now`;
  `client.ts` wraps every call and calls `clock.observe(data.now)`; `providers.tsx` subscribes the clock to
  `queryClient.invalidateQueries` for student keys.

- [ ] **Step 5:** Clock test:

```ts
// web/tests/unit/clock.test.ts
import { it, expect, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import { clock, bindClockToQueries } from "../../src/session/clock";

it("clock change invalidates student queries", () => {
  const qc = new QueryClient();
  const spy = vi.spyOn(qc, "invalidateQueries");
  bindClockToQueries(qc);
  clock.observe("2026-10-12T09:00:00-04:00");
  spy.mockClear();
  clock.observe("2026-10-12T09:00:00-04:00");
  expect(spy).not.toHaveBeenCalled();
  clock.observe("2026-10-13T12:15:00-04:00");
  expect(spy).toHaveBeenCalled();
});
```

- [ ] **Step 6:** `npx vitest run` green; `npm run build` succeeds; `npx tsc --noEmit` clean.
- [ ] **Step 7:** Tokens (`tokens.css` from spec §5.1, Tailwind `@theme` mapping `--color-*` to the variables), fonts
  imported in `main.tsx`, `index.html` viewport + theme-color. Commit `feat(web): scaffold, typed client, transport with inspector, session and clock`.

## Task 5: UI kit, app shell, entry screen

**Files:** `web/src/ui/*.tsx` (Button, IconButton, Chip, Card, Badge, Skeleton, Sheet, Dialog, Banner, TabBar,
TopBar, ClockPill, ProgressBar, Bars, EmptyState, ErrorState, LiveRegion, DimensionIcon), `web/src/app/Shell.tsx`,
`web/src/features/entry/Entry.tsx`, `web/tests/component/ui.test.tsx`, `web/playwright.config.ts`,
`web/tests/e2e/screens.spec.ts` (screenshot harness).

- [ ] **Step 1:** Component tests: Button shows a spinner and is `disabled` + `aria-busy` while `loading`; Sheet traps
  focus, closes on Escape, returns focus to its trigger; TabBar marks the current tab with `aria-current="page"`;
  Badge for `synthetic` renders "Sample".
- [ ] **Step 2:** Implement the kit to spec §5 (sizes, radii, motion tokens, reduced motion via `useReducedMotion`).
  Sheet: bottom sheet on phones (drag handle + close button), centred dialog ≥ 768 px.
- [ ] **Step 3:** Shell: TopBar (title, inbox bell with unread badge, ClockPill), content area with bottom padding
  for the TabBar + safe-area inset, TabBar (Today/Map/Campus/You). Route change focuses the page `<h1>`.
- [ ] **Step 4:** Entry screen per spec §7.1 using `api.personas()`; selecting a persona starts a session and
  navigates (`/focus` if `map.profile.focus` is null, else `/next`).
- [ ] **Step 5:** Playwright screenshot harness: for a list of routes, open at 390×844 light and dark, save to
  `web/test-results/screens/<route>-<scheme>.png`. Run it; **read the screenshots** and fix anything off-spec
  (spacing rhythm, hierarchy, contrast, truncation).
- [ ] **Step 6:** Commit `feat(web): UI kit, shell, entry`.

## Task 6: Focus flow, Today, care-first, crisis

**Files:** `web/src/features/focus/*`, `web/src/features/today/{Today,StepCard,WhySheet,DeclineSheet,Alternates,SupportFirst}.tsx`,
`web/src/features/safety/CrisisScreen.tsx`, tests `web/tests/component/{focus,today,crisis}.test.tsx`.

**Interfaces:** emits signals `focus:submitted`, `next:shown`, `why:opened`, `crisis:shown`, `decline:done`.
Elements carry `data-tour` ids: `pick-dimension`, `barrier-<id>`, `own-words`, `focus-submit`, `step-card`,
`why-open`, `im-in`, `not-for-me`, `support-card`.

- [ ] **Step 1: Failing tests** (MSW serves backend fixtures):
  - Focus: growth areas are highlighted but not selected; submit disabled until one dimension is chosen; barriers
    multi-select; submitting `me_focus_crisis.json` renders the crisis screen and the typed text appears nowhere in
    the DOM.
  - Today: Andre fixture renders title, "Fits your Tuesday gap, 12:20–2:30", "Free", "14 Newark students are going",
    "Sample" badge; Why sheet lists five components with their weight percentages and the footer sentence.
  - Taylor fixture: support card is first; no "I'm in" visible until "Prefer something small to do?" is tapped.
  - Crisis: each line is a link with the right `href` (`tel:988`, `sms:741741?&body=HOME`); unverified shows
    "Verifying".
- [ ] **Step 2:** Implement per spec §7.2, §7.3, §7.5, §7.6, including the finding checklist (ticks driven by the
  pending mutation; "Ranking {N}" uses `call.trace.candidates` when present, otherwise "Ranking Rutgers events and
  services").
- [ ] **Step 3:** Tests green; screenshots reviewed.
- [ ] **Step 4:** Commit `feat(web): focus flow, next step, why, care-first, crisis`.

## Task 7: Plan, calendar, invite, friend page

**Files:** `web/src/features/plan/{PlanView,usePlan}.tsx`, `web/src/features/invite/InvitePage.tsx`, tests.

- [ ] **Step 1: Failing tests:** tapping "I'm in" twice sends one `POST /commitments`; plan view shows `plan_text`,
  "We'll remind you at 12:15 PM"; "Add to calendar" links to `${API}/commitments/{id}/ics?...` and the Google URL;
  share uses `navigator.share` when present else copies `${origin}/i/{token}` and toasts "Link copied"; invite page
  shows the note and "I'll come" → "You're in".
- [ ] **Step 2:** Implement per spec §7.4 and §7.13 with the `layoutId` card→plan morph. The plan route reads the
  commitment from the query cache (set on commit) and falls back to the inbox/next data if opened cold; if neither
  has it, show "This plan is in your You tab" with a link (no plan read endpoint exists).
- [ ] **Step 3:** Commit `feat(web): plan, calendar, invite`.

## Task 8: Time sheet, banners, inbox, follow-up (Checkpoint B: whole Andre loop by hand)

**Files:** `web/src/features/time/TimeSheet.tsx`, `web/src/features/inbox/{Inbox,NotificationBanner}.tsx`,
`web/src/features/followup/{Followup,FollowupResult,WinPrompt}.tsx`, tests.

- [ ] **Step 1: Failing tests:** skip-ahead response with one `fired` item shows one banner with title/body and
  `role="status"`; tapping it navigates to the deep link; follow-up requires "Did you go?" before "Did it help?";
  submit sends once; result renders lines in order: progress message, Arc "(demo)", challenge bar from
  `progress - added` to `progress`, learned facts with source labels, next-rung message, win prompt; win submit with
  `win_crisis.json` shows the crisis screen.
- [ ] **Step 2:** Implement per spec §7.7, §7.8, §9.5 (presets: next due, +1 day, Tue Oct 13 12:15 PM, Tue Oct 13
  3:30 PM, Mon Oct 19 9:00 AM, Tue Oct 27 9:00 AM; Reset only when `session.stage`).
- [ ] **Step 3: Checkpoint B.** Run the RUNBOOK Andre script by hand in the browser against production with a
  sandbox session. Every step works. Screenshots of each screen reviewed.
- [ ] **Step 4:** Commit `feat(web): time travel, notifications, inbox, follow-up loop`.

## Task 9: Map, You, Campus, Ask, MyRutgers card, Spanish

**Files:** `web/src/features/{map,you,campus,ask,card}/*`, `web/src/i18n/es.ts`, tests including
`web/tests/unit/i18n.test.ts` (every `en` key exists in `es`).

- [ ] **Step 1: Failing tests:** map sorts by score with strengths first and shows "from the inventory on Sep 14";
  with `previous_takes`, social shows "↑ 0.5"; memory delete removes the row optimistically and calls DELETE once;
  "Delete all" and "Forget me" require confirmation; Same here increments optimistically and rolls back on error;
  Ask with a crisis response shows the crisis card; Sofia's fixture switches UI chrome to Spanish.
- [ ] **Step 2:** Implement per spec §7.9–§7.12 and §7.14.
- [ ] **Step 3:** Commit `feat(web): map, you and memory, campus, ask, card, Spanish`.

## Task 10: Staff Pulse

**Files:** `web/src/features/staff/{StaffLayout,Overview,Gaps,Trends,AskData,Filters,SuppressedCell}.tsx`,
`web/src/ui/charts/{Funnel,HBar,Line}.tsx`, tests.

- [ ] **Step 1: Failing tests:** suppressed values render "Under 10" hatched cells, never a number or zero;
  `suppressed_groups` appears in the header line; gaps callout picks the top Camden row and compares to Newark's
  same dimension; Ask the data shows the SQL in a `<pre>` and a table; every chart has a visually hidden table
  equivalent and a one-line summary.
- [ ] **Step 2:** Implement per spec §8 with lazy route chunk. Charts are SVG with direct labels, tabular numbers,
  midterms band as a labelled hatched rect.
- [ ] **Step 3:** Commit `feat(web): Staff Pulse`.

## Task 11: Demo engine, story script, table tours

**Files:** `web/src/demo/{types,story,tours,engine}.ts`, `web/src/demo/coach/{CoachBar,Spotlight}.tsx`,
`web/src/features/tour/{TourHome,TourDone}.tsx`, `web/tests/unit/engine.test.ts`.

**Interfaces:**

```ts
// web/src/demo/types.ts
export type Persona = "andre" | "priya" | "taylor" | "sofia" | "jordan" | "staff";
export type Signal =
  | "focus:submitted" | "next:shown" | "why:opened" | "commitment:created" | "invite:shared" | "push:enabled"
  | "notification:shown" | "followup:submitted" | "memory:deleted" | "map:shown" | "crisis:shown" | "staff:gaps"
  | "staff:suppressed" | "staff:asked" | "ask:answered";
export type Action =
  | { kind: "tap"; target: string }
  | { kind: "type"; target: string; text: string; submit?: string }
  | { kind: "navigate"; to: string }
  | { kind: "skip"; to: "next_due" | string }
  | { kind: "clock"; now: string }
  | { kind: "session"; persona: Persona; sandbox: boolean }
  | { kind: "templates"; on: boolean };
export type ProofKind = "fit" | "latency" | "safety" | "plan" | "push" | "memory" | "score" | "funnel" | "gaps" | "sql" | "suppression" | "none";
export type StoryStep = {
  id: string; chapter: string; persona: Persona | null; route?: string; target?: string;
  perform?: Action[]; waitFor?: Signal; claim: string; proof?: ProofKind; note?: string;
  tag?: "Impact" | "Engagement" | "Safety" | "Equity" | "Feasibility" | "Privacy"; slide?: "cold-open" | "close";
};
export type EngineState = { steps: StoryStep[]; index: number; done: Set<string>; history: number[] };
export type EngineEvent = { type: "next" } | { type: "back" } | { type: "jump"; index: number } | { type: "signal"; name: Signal } | { type: "restart" };
```

- [ ] **Step 1: Failing engine tests**

```ts
// web/tests/unit/engine.test.ts
import { describe, it, expect } from "vitest";
import { reduce, init } from "../../src/demo/engine";
import { MAIN_STORY } from "../../src/demo/story";
import { TOURS } from "../../src/demo/tours";

describe("demo engine", () => {
  it("advances on next and on the awaited signal", () => {
    let s = init(MAIN_STORY);
    const i = MAIN_STORY.findIndex(x => x.waitFor === "commitment:created");
    s = reduce(s, { type: "jump", index: i });
    s = reduce(s, { type: "signal", name: "next:shown" });
    expect(s.index).toBe(i);
    s = reduce(s, { type: "signal", name: "commitment:created" });
    expect(s.index).toBe(i + 1);
  });
  it("back returns to the previous visited step", () => {
    let s = init(MAIN_STORY);
    s = reduce(s, { type: "next" }); s = reduce(s, { type: "next" });
    s = reduce(s, { type: "back" });
    expect(s.index).toBe(1);
  });
  it("never goes past the end or before the start", () => {
    let s = init(MAIN_STORY);
    s = reduce(s, { type: "back" });
    expect(s.index).toBe(0);
    s = reduce(s, { type: "jump", index: 999 });
    expect(s.index).toBe(MAIN_STORY.length - 1);
  });
  it("every step that waits for a signal also has a perform action or target", () => {
    for (const st of [...MAIN_STORY, ...Object.values(TOURS).flat()]) {
      if (st.waitFor) expect(Boolean(st.perform?.length || st.target)).toBe(true);
    }
  });
  it("tours use sandbox sessions only", () => {
    for (const tour of Object.values(TOURS)) {
      for (const st of tour) for (const a of st.perform ?? []) if (a.kind === "session") expect(a.sandbox).toBe(true);
    }
  });
  it("main story stays within 12 chapters and starts and ends with slides", () => {
    const chapters = new Set(MAIN_STORY.map(s => s.chapter));
    expect(chapters.size).toBeLessThanOrEqual(12);
    expect(MAIN_STORY[0].slide).toBe("cold-open");
    expect(MAIN_STORY.at(-1)!.slide).toBe("close");
  });
});
```

- [ ] **Step 2:** Implement `engine.ts` (pure reducer; `next` pushes index to history; `signal` advances only when it
  matches the current step's `waitFor`). Write `story.ts` from spec §9.2 (one entry per row, split into the
  sub-steps the table shows; claims and notes verbatim from the spec; dates exactly: Mon Oct 12 9:00, reminder Tue
  Oct 13 12:15, follow-up Tue Oct 13 3:30 PM, Mon Oct 19 9:00, retake view Tue Oct 27 9:00). Write `tours.ts`:
  `andre` (7 steps), `priya` (5), `taylor` (4), `sofia` (3), `jordan` (4), `staff` (4), every first step a
  `session` action with `sandbox: true`.
- [ ] **Step 3:** Coach bar + spotlight (spec §9.4): spotlight is a positioned ring + dim overlay with
  `pointer-events: none` except a cut-out around the target; it tracks the target with `ResizeObserver` and
  scrolls it into view; it never sets `aria-hidden` on content.
- [ ] **Step 4:** Tour home + completion card. Tests green; play each tour by hand on a 390 px viewport.
- [ ] **Step 5:** Commit `feat(demo): story engine, table tours, coach bar`.

## Task 12: Stage mode (Checkpoint C: the full stage story)

**Files:** `web/src/demo/present/{Present,PhoneFrame,Rail,Proof*,RequestLog,Slides,Keys,bridge}.tsx`,
`web/src/demo/bridge.ts` (postMessage protocol), `web/tests/e2e/stage.spec.ts`.

**Interfaces (bridge, same-origin only):**
- parent → iframe: `{ kind: "perform"; actions: Action[] }`, `{ kind: "navigate"; to: string }`
- iframe → parent: `{ kind: "call"; call: CallLog }`, `{ kind: "signal"; name: Signal; data?: unknown }`,
  `{ kind: "ready"; route: string }`
- The iframe loads `/?embed=stage` which uses the stage session token passed via `#t=` (not stored outside the tab).

- [ ] **Step 1:** Implement layout per spec §9.3 at 1280×720 and 1920×1080 (phone scaled with CSS `transform` from a
  fixed 390×844 iframe). Performer inside the app: `tap` shows a ripple at the target centre then calls `.click()`;
  `type` types at ~28 chars/s into the input then optionally taps `submit`.
- [ ] **Step 2:** Proof panels: `fit` (bars from the last `/me/next` pick), `latency` (request log), `safety`
  (pipeline diagram: "Your words → code check {safety_ms} ms → crisis card; AI never saw it" when `trace.safety=lexicon`),
  `plan` (plan sentence + implementation-intentions citation), `push` (receipt from the paired device or "banner
  shown in-app"), `memory`, `score`, `gaps`, `suppression`, `sql`, `funnel`.
- [ ] **Step 3:** Keys per spec §9.3. `A` toggles `POST /demo/force-templates` and the mode badge; `R` asks to confirm,
  then `POST /demo/reset`, waits for `/health`, starts a fresh stage session and returns to step 0.
- [ ] **Step 4:** Playwright `stage.spec.ts` (1280×720): press `→` through the entire main story against production;
  assert the rail chapter titles in order, the lunch title, the banner, "2.4" on the map, the crisis title, the staff
  callout; total under 4 minutes of wall time with default pauses removed.
- [ ] **Step 5: Checkpoint C.** Run the stage story three times in a row with no manual recovery; once with `A`
  (templates). Screenshots of every chapter reviewed.
- [ ] **Step 6:** Commit `feat(demo): stage presenter with live evidence rail`.

## Task 13: Push, pairing, offline replay

**Files:** `web/public/{manifest.webmanifest,sw.js,icons/*}`, `web/src/push/push.ts`, `web/src/demo/pair/{PairQR,Join}.tsx`,
`web/src/demo/replay/{replay.ts,recording.json}`, `web/scripts/record-story.ts`, tests
`web/tests/unit/replay.test.ts`, `web/tests/e2e/offline.spec.ts`.

- [ ] **Step 1: Push.** `sw.js`: on `push`, show notification (title/body from payload, `data.deep_link`), post a
  receipt to open clients; on `notificationclick`, focus/open the deep link. `push.ts`: register SW, get VAPID key,
  subscribe on user gesture, `POST /push/subscriptions`. Verify on a real Android phone (or installed iOS PWA):
  stage skip-ahead → phone shows "Commuter lunch and board games starts in 15 minutes".
- [ ] **Step 2: Pairing.** `P` on stage shows a QR (`qrcode`) for `${origin}/join#t=<token>`; `/join` stores the token
  for that tab and routes to `/you` with the reminders toggle highlighted.
- [ ] **Step 3: Replay tests**

```ts
// web/tests/unit/replay.test.ts
import { it, expect, beforeEach } from "vitest";
import { loadReplay, replayRequest } from "../../src/demo/replay/replay";

beforeEach(() => loadReplay({
  calls: [
    { method: "GET", path: "/me/next", status: 200, body: { now: "a", pick: { rec_id: 1 } } },
    { method: "POST", path: "/commitments", status: 200, body: { now: "a", commitment_id: 9 } },
    { method: "GET", path: "/me/next", status: 200, body: { now: "b", pick: null } },
  ],
  fixtures: { "GET /me/inbox": { now: "x", items: [] } },
}));

it("replays matching calls in recorded order, then repeats the last", async () => {
  expect((await replayRequest<any>("GET", "/me/next")).data.pick.rec_id).toBe(1);
  expect((await replayRequest<any>("POST", "/commitments", { rec_id: 1 })).data.commitment_id).toBe(9);
  expect((await replayRequest<any>("GET", "/me/next")).data.pick).toBeNull();
  expect((await replayRequest<any>("GET", "/me/next")).data.pick).toBeNull();
});

it("falls back to persona fixtures, then to a clear error", async () => {
  expect((await replayRequest<any>("GET", "/me/inbox")).data.items).toEqual([]);
  await expect(replayRequest("GET", "/staff/funnel")).rejects.toThrow(/not available offline/i);
});

it("normalises ids in paths", async () => {
  loadReplay({ calls: [{ method: "POST", path: "/followups/3096", status: 200, body: { now: "c" } }], fixtures: {} });
  expect((await replayRequest<any>("POST", "/followups/7")).data.now).toBe("c");
});
```

- [ ] **Step 4:** Implement replay (key = method + path with numeric/token segments replaced by `:id`; per-key queue;
  last response sticks; fixtures from `../fixtures/<persona>/*.json` bundled via `import.meta.glob`, mapped by
  endpoint). `record-story.ts` runs the main story's API calls in order against production on a sandbox session and
  writes `recording.json`. Auto-switch to replay after 3 consecutive network/5xx failures, with a toast and badge.
- [ ] **Step 5:** Playwright `offline.spec.ts`: start stage story live, block all API routes after chapter 2, keep
  pressing `→` to the end; the badge reads "Offline replay" and every chapter renders.
- [ ] **Step 6:** Commit `feat(demo): web push, phone pairing, offline replay`.

## Task 14: Deploy, end-to-end on production, rehearsal docs

**Files:** Create `infra/web_stack.py`; modify `infra/app.py`, `scripts/deploy.py` (add `--web`), `docs/RUNBOOK.md`
(demo-day section for the web app), `README.md`, `docs/DECISIONS.md` (26+).

- [ ] **Step 1: CDK stack**

```python
# infra/web_stack.py
from aws_cdk import Stack, CfnOutput, RemovalPolicy, Duration
from aws_cdk import aws_s3 as s3, aws_cloudfront as cf, aws_cloudfront_origins as origins, aws_s3_deployment as deploy
from constructs import Construct


class WebStack(Stack):
    def __init__(self, scope: Construct, cid: str, *, dist_dir: str, **kw) -> None:
        super().__init__(scope, cid, **kw)
        bucket = s3.Bucket(self, "Site", block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                           removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True)
        dist = cf.Distribution(
            self, "Cdn",
            default_behavior=cf.BehaviorOptions(origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                                                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                                                cache_policy=cf.CachePolicy.CACHING_OPTIMIZED),
            default_root_object="index.html",
            error_responses=[cf.ErrorResponse(http_status=s, response_http_status=200, response_page_path="/index.html",
                                              ttl=Duration.seconds(0)) for s in (403, 404)],
        )
        deploy.BucketDeployment(self, "Deploy", sources=[deploy.Source.asset(dist_dir)], destination_bucket=bucket,
                                distribution=dist, distribution_paths=["/*"])
        CfnOutput(self, "WebUrl", value=f"https://{dist.distribution_domain_name}")
```

  `index.html` and `sw.js` get `Cache-Control: no-cache` (second `BucketDeployment` with `include` filters, or
  `cache_control` on a dedicated source); hashed assets stay cached.
- [ ] **Step 2:** `scripts/deploy.py --web`: `npm ci && npm run build` in `web/` with `VITE_API_BASE` set, then
  `cdk deploy CompassWeb --require-approval never`, print the URL. Run it.
- [ ] **Step 3:** Playwright full suite against the deployed web URL (phone + stage projects), including table tours
  for all personas in parallel (proves sandbox isolation end to end).
- [ ] **Step 4:** Screenshot review in light and dark at 375 px and 1280 px; fix anything off-spec; redeploy.
- [ ] **Step 5:** RUNBOOK: stage checklist (reset, pair phone, test push, `A`/`O` drills), table setup (QR card URL),
  failure drills. Record a backup screen capture of the stage story (manual, by the team).
- [ ] **Step 6:** Commit `feat(deploy): CompassWeb stack; e2e on production; demo-day runbook`.

## Task 15 (P2, only if time remains): map and polish

- Campus map for the next step's venue (MapLibre + OpenFreeMap positron, lazy chunk, address fallback).
- Count-up animations for the Cup bar and the 1.9 → 2.4 retake change (reduced-motion: instant).
- Lighthouse pass on phone profile; fix anything under 90 in Performance/Accessibility.

## Checkpoints for the user

- **A (after Task 5):** screenshots of the shell and entry. Design check-in; work continues unless told otherwise.
- **B (after Task 8):** the whole Andre loop works by hand on production.
- **C (after Task 12):** stage story runs three times clean. This is the minimum to present.
- Table tours (Task 11) and offline replay (Task 13) make it robust; Staff (Task 10) completes the pitch.

Order if time runs short: 1 → 4 → 5 → 6 → 7 → 8 → 12 (stage, using non-sandbox sessions) → 10 → 14 (deploy) → 2 → 11
→ 13 → 3 → 9 → 15.
