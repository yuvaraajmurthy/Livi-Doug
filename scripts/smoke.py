"""Smoke test: the acceptance scenarios end to end against a running API.

  python -m scripts.smoke http://localhost:8000
  python -m scripts.smoke https://<cloudfront>.cloudfront.net --reset
"""
import json
import statistics
import sys
import time
from pathlib import Path

import httpx
import yaml

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
RESET = "--reset" in sys.argv
QUICK = "--quick" in sys.argv
LAT: dict[str, list[float]] = {}
FAILS: list[str] = []
c = httpx.Client(base_url=BASE, timeout=30)


def _route_key(method: str, path: str) -> str:
    parts = [("{id}" if (p.isdigit() or len(p) > 20 or p.startswith(("m:", "w-"))) else p) for p in path.split("?")[0].split("/")]
    return f"{method} " + "/".join(parts)


def call(method: str, path: str, token: str | None = None, **kw) -> httpx.Response:
    h = {"Authorization": f"Bearer {token}"} if token else {}
    t = time.perf_counter()
    r = c.request(method, path, headers=h, **kw)
    LAT.setdefault(_route_key(method, path), []).append(time.perf_counter() - t)
    return r


def check(name: str, cond, detail: str = "") -> None:
    ok = bool(cond)
    print(("  PASS " if ok else "  FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def session(persona: str) -> str:
    return call("POST", "/demo/session", json={"persona": persona}).json()["token"]


def andre() -> None:
    print("Andre end to end")
    t = session("andre")
    m = call("GET", "/me/map", t).json()
    check("map strengths first (spiritual)", m["dimensions"][0]["dimension"] == "spiritual", m["dimensions"][0]["dimension"])
    check("map social 1.9 is low", next(d for d in m["dimensions"] if d["dimension"] == "social")["band"] == "low")
    f = call("POST", "/me/focus", t, json={"dimension": "social", "barriers": ["no_time", "dont_know_anyone"]}).json()
    check("focus saved, rung 2", f.get("kind") == "profile" and f["profile"]["social_rung"] == 2, json.dumps(f)[:200])
    n = call("GET", "/me/next", t).json()
    p = n["pick"]
    check("pick is the commuter lunch", p["item"]["id"] == "pin-andre-lunch-2026-10-13", p["item"]["id"])
    check("pick in Tuesday window", (p.get("window_label") or "").startswith("Fits your Tuesday"), str(p.get("window_label")))
    check("pick rung 2", p["rung"] == 2)
    check("going 14", p["going"]["count"] == 14, json.dumps(p["going"]))
    check("reasons have 5 components", len(p["reasons"]["components"]) == 5)
    check("why line present", len(p["why"]) > 10, p["why"])
    check("2 alternates", len(n["alternates"]) == 2)
    cm = call("POST", "/commitments", t, json={"rec_id": p["rec_id"]}).json()
    check("commit planned with invite", cm.get("kind") == "commitment" and cm.get("invite_token"), json.dumps(cm)[:200])
    check("reminder 12:15", (cm.get("reminder_at") or "").startswith("2026-10-13T12:15"), str(cm.get("reminder_at")))
    inv = call("GET", f"/invites/{cm['invite_token']}").json()
    blob = json.dumps(inv).lower()
    check("invite works without account, no student data",
          inv["item"]["id"] == p["item"]["id"] and "demo-andre" not in blob and "score" not in blob)
    acc = call("POST", f"/invites/{cm['invite_token']}").json()
    check("friend accepts", acc.get("accepted") is True)
    ics = call("GET", cm["ics_url"])
    check("ics file", ics.status_code == 200 and "BEGIN:VEVENT" in ics.text)
    s1 = call("POST", "/demo/skip-ahead", t, json={"to": "next_due"}).json()
    kinds = [x["kind"] for x in s1["fired"]]
    check("skip 1 fires reminder", kinds == ["reminder"], str(kinds))
    check("reminder pushed (inside budget, outside quiet hours)", s1["fired"] and s1["fired"][0]["delivered"] == "push")
    s2 = call("POST", "/demo/skip-ahead", t, json={"to": "next_due"}).json()
    check("skip 2 fires follow-up", [x["kind"] for x in s2["fired"]] == ["followup"], str([x["kind"] for x in s2["fired"]]))
    fu = call("POST", f"/followups/{cm['commitment_id']}", t, json={"went": True, "helped": 4}).json()
    check("arc credit", fu.get("arc", {}).get("status") == "mock", json.dumps(fu)[:300])
    check("challenge progress (+2 with friend)", fu.get("challenge") and fu["challenge"]["added"] == 2, json.dumps(fu.get("challenge")))
    check("next rung 3 offered", fu.get("next_rung") and fu["next_rung"]["rung"] == 3)
    check("memory learned games", any(m["statement"] == "You enjoyed game-based events" for m in fu.get("learned", [])),
          json.dumps(fu.get("learned"))[:300])
    dup = call("POST", f"/followups/{cm['commitment_id']}", t, json={"went": True, "helped": 4})
    check("second follow-up is 409", dup.status_code == 409)
    mem = call("GET", "/me/memory", t).json()
    games = next((m for m in mem["items"] if m["kind"] == "likes_format" and m["statement"] == "You enjoyed game-based events"), None)
    check("memory lists game fact", games is not None)
    call("POST", "/demo/clock", t, json={"now": "2026-10-19T09:00:00-04:00"})
    n2 = call("GET", "/me/next", t).json()
    check("week 2 pick is basketball rung 3",
          n2["pick"]["item"]["id"] == "pin-andre-basketball-2026-10-22" and n2["pick"]["rung"] == 3, n2["pick"]["item"]["id"])
    cites = [r["memory_id"] for r in n2["pick"]["reasons"]["memory"]]
    check("reasons cite the memory", games and games["id"] in cites, str(cites))
    if games:
        call("DELETE", f"/me/memory/{games['id']}", t)
        n3 = call("GET", "/me/next", t).json()
        check("after delete, reasons stop citing it", games["id"] not in [r["memory_id"] for r in n3["pick"]["reasons"]["memory"]])
    call("POST", "/demo/clock", t, json={"now": "2026-10-27T09:00:00-04:00"})
    m2 = call("GET", "/me/map", t).json()
    check("later take shows social 2.4", next(d for d in m2["dimensions"] if d["dimension"] == "social")["score"] == 2.4)


def taylor() -> None:
    print("Taylor care-first")
    t = session("taylor")
    m = call("GET", "/me/map", t).json()
    check("care_first on map", m["care_first"] is True)
    n = call("GET", "/me/next", t).json()
    check("support card first, NB", n["care_first"] and n["support_card"] and n["support_card"]["options"][0]["campus"] == "new_brunswick")
    check("no event pushed", all(not s["pushed"] for s in [n["pick"], *n["alternates"]]))
    check("crisis lines visible", len(n["crisis_lines"]) >= 4)


def priya() -> None:
    print("Priya")
    t = session("priya")
    call("POST", "/me/focus", t, json={"dimension": "physical", "barriers": ["coursework"]})
    p = call("GET", "/me/next", t).json()["pick"]
    check("Busch Learning Center", p["item"]["id"] == "res-nb-023", p["item"]["title"])
    check("real address + source", "Frelinghuysen" in (p["where"]["address"] or "") and p["source"]["name"] and not p["item"]["synthetic"])


def sofia() -> None:
    print("Sofia")
    t = session("sofia")
    call("POST", "/me/focus", t, json={"dimension": "financial", "barriers": ["no_time", "money"]})
    n = call("GET", "/me/next", t).json()
    picks = [n["pick"], *n["alternates"]]
    check("Camden or online only", all(s["where"]["campus"] in ("camden", "online") for s in picks), str([s["where"]["campus"] for s in picks]))
    check("Spanish wording", n["pick"]["cost_label"] in ("Gratis", "Costo no indicado", "Con costo"), n["pick"]["why"])
    st = session("staff")
    g = call("GET", "/staff/gaps?dimension=financial", st).json()
    check("Camden is the largest financial gap", g["rows"][0]["campus"] == "camden", json.dumps(g["rows"][:2]))


def crisis_all() -> None:
    print("Crisis set through every free-text endpoint")
    phrases = yaml.safe_load((Path(__file__).resolve().parent.parent / "tests" / "safety" / "phrases.yaml").read_text(encoding="utf-8"))
    t = session("jordan")
    crisis = phrases["crisis"][::5] if QUICK else phrases["crisis"]
    bad = []
    for ph in crisis:
        r1 = call("POST", "/me/focus", t, json={"dimension": "social", "text": ph}).json()
        r2 = call("POST", "/wins", t, json={"text": ph[:140]}).json()
        if r1.get("kind") != "crisis" or r2.get("kind") != "crisis":
            bad.append(ph)
    check(f"{len(crisis)} crisis phrases -> crisis card (focus + wins)", not bad, str(bad[:5]))
    fa = []
    for ph in phrases["false_alarms"][:10]:
        r = call("POST", "/me/focus", t, json={"dimension": "social", "text": ph}).json()
        if r.get("kind") == "crisis":
            fa.append(ph)
    check("false alarms pass through", not fa, str(fa))
    pulse = call("GET", "/pulse", t).json()
    check("no crisis text on the wall", not any(p.lower()[:20] in w["text"].lower() for w in pulse["wins"] for p in crisis))


def wins() -> None:
    print("Wins moderation")
    t = session("jordan")
    a = call("POST", "/wins", t, json={"text": "Ate lunch on campus instead of in my car. Small thing, felt good.", "dimension": "social"}).json()
    check("normal post approved", a.get("kind") == "accepted", json.dumps(a))
    b = call("POST", "/wins", t, json={"text": "Went to yoga with Jessica and it was great", "dimension": "physical"}).json()
    check("post with a name held", b.get("kind") == "held", json.dumps(b))


def staff() -> None:
    print("Staff")
    st = session("staff")
    f = call("GET", "/staff/funnel", st).json()
    check("funnel rows, all groups >= 10", f["rows"] and all(r["students"] >= 10 for r in f["rows"]))
    w = call("GET", "/staff/weekly?first_gen=true&housing=commuter&level=grad", st).json()
    check("filtered weekly never shows n < 10", all(p["n"] >= 10 for p in w["points"]))
    d = call("GET", "/staff/dips", st).json()
    tagged = [x for x in d["dips"] if x["overlay"]]
    check("dips line up with calendar", d["dips"] and len(tagged) >= len(d["dips"]) * 0.6, f"{len(tagged)}/{len(d['dips'])}")
    r = call("GET", "/staff/retakes", st).json()
    check("users retake more than non-users", r["rows"] and all(x["users_rate"] > x["non_users_rate"] for x in r["rows"]))


def main() -> None:
    if RESET:
        print("reset", call("POST", "/demo/reset").json())
    for fn in (andre, taylor, priya, sofia, wins, staff, crisis_all):
        try:
            fn()
        except Exception as exc:
            FAILS.append(f"{fn.__name__}: {exc!r}")
            print("  ERROR", fn.__name__, repr(exc)[:300])
    print("\nLatency by route (s):")
    for k, v in sorted(LAT.items()):
        v = sorted(v)
        print(f"  {k:42s} n={len(v):3d} p50={statistics.median(v):.3f} p95={v[min(len(v) - 1, int(len(v) * 0.95))]:.3f}")
    print("\nRESULT:", "ALL PASS" if not FAILS else f"{len(FAILS)} FAIL: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
