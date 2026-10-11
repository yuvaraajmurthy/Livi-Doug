# API contract changelog

Frontend: read this before each pull. Additive changes only after v1 unless flagged **BREAKING**.

## v1.2.0 (2026-10-10, late night): additive only

- `POST /demo/session {persona, sandbox: true}` gives the session a private copy of the persona (`student_id` like
  `DEMO-ANDRE~sb…`). Use it for table-mode tours so concurrent judges never share state. Staff aggregates exclude
  sandbox students; `/demo/reset` deletes them; they also expire after 6 hours.

## v1.1.0 (2026-10-10, Sat night): additive only

- **Live data behind every route** (fixtures remain the automatic fallback; header `X-Compass-Fallback`).
- `POST /ask {question}` → `{kind: "answer"|"redirect", text, items[], source}` or `{kind: "crisis", ...}`. Questions about Rutgers resources/events only; medication/diagnosis questions get a redirect to people.
- `POST /staff/ask {question}` (staff token) → `{ok, message, sql, columns, rows}`. Show `sql` to the user. Read-only, groups under 10 never included.
- `POST /v1/chat/completions` (OpenAI-compatible, `stream: true` supported) for ElevenLabs custom LLM. Put a student demo token in the custom LLM's API key field.
- `GET /me/next`: `pick.source` now carries real attribution (e.g. "ScarletWell Wellness Calendar", "via Scarlet Sync (student project)", "Compass research (verified)") and `verified_on`.
- `GET /pulse`: challenges include the student's residence-hall challenge (Jordan: Livingston halls).
- `FollowupResponse.learned[]` lists what Compass just learned (link these to the "What Compass knows" screen).
- `POST /demo/reset` takes ~2 s on AWS and re-warms AI wording in the background (~1 min).

## v1.0.0 (2026-10-10, Sat evening)

First published contract. `contract/openapi.json` is generated from the code (`python -m scripts.export_openapi`).

How to use it:
1. `POST /demo/session {"persona": "andre"}` → `token`. Personas: andre, priya, taylor, sofia, jordan, staff.
2. Send `Authorization: Bearer <token>` on every `/me/*`, `/commitments`, `/followups/*`, `/pulse`, `/wins`, `/push/*`, `/staff/*` call.
3. `/invites/{token}` is public (the friend's page). `/health`, `/demo/personas`, `/meta/barriers` are public.

Shapes to know:
- Every response has `synthetic` (badge it) and `now` (simulated time, America/New_York). Show `now` in the demo shell.
- Header `X-Compass-Fallback: fixture` means the response came from a fixture; `template` means wording came from templates.
- `POST /me/focus`, `POST /wins`, `POST /commitments` can return `{"kind": "crisis", ...}` instead of the normal shape. Switch on `kind`. The crisis card is fixed copy plus `lines[]`; render every line, call/text buttons from `href`. Lines with `verified: false` get a small "verify" badge outside production.
- `GET /me/next`: if `care_first` is true, render `support_card` first (a person, not an event). Events still arrive with `pushed: false`.
- `Suggestion.reasons` is structured: `filters[]`, `components[]` (name, weight, score, contribution, text), `memory[]` (things Compass learned, each with `memory_id` so the "What Compass knows" screen can link to it), `distance`, `total`. `why` is the one-liner on top; `why_source` says `ai` or `template`.
- `going.count` is only set from 5 up; otherwise show `going.label` (may be empty).
- `GET /me/memory` is the "What Compass knows" screen. `DELETE /me/memory/{id}`, `DELETE /me/memory`, `DELETE /me` (forget me).
- `POST /demo/skip-ahead {"to": "next_due"}` advances the session clock to the next due notification and fires it; also accepts `"+2d"`, `"+3h"`, or an ISO datetime. Response lists `fired[]` so the demo shell can show a fake lock-screen push even without real push.
- Push: `GET /push/vapid-key`, then `POST /push/subscriptions` with the browser's `PushSubscription.toJSON()` (`endpoint`, `keys.p256dh`, `keys.auth`). `?test=true` sends a test push.

Run the fixture server locally:
```
pip install -r requirements.txt
MODE=fixtures uvicorn app.main:app --port 8000      # PowerShell: $env:MODE="fixtures"; uvicorn app.main:app
open http://localhost:8000/docs
```
