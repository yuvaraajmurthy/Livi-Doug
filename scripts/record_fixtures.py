"""Re-record fixtures from a live API so fixture mode returns exactly what the live API returns.
Every recorded body is validated against its response model before it is written.

  python -m scripts.record_fixtures https://d2fap8zqnl1gn5.cloudfront.net
"""
import json
import sys
from pathlib import Path

import httpx
from pydantic import TypeAdapter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests" / "contract"))
from test_contract import REGISTRY  # noqa: E402

BASE = sys.argv[1].rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "fixtures"
c = httpx.Client(base_url=BASE, timeout=60)
FOCUS = {
    "andre": {"dimension": "social", "barriers": ["no_time", "dont_know_anyone"]},
    "priya": {"dimension": "physical", "barriers": ["coursework"]},
    "taylor": {"dimension": "emotional", "barriers": []},
    "sofia": {"dimension": "financial", "barriers": ["no_time", "money"]},
    "jordan": {"dimension": "social", "barriers": ["dont_know_anyone", "not_my_scene"]},
}


def save(persona: str, key: str, body: dict) -> None:
    TypeAdapter(REGISTRY[key]).validate_python(body)
    d = OUT / persona
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.json").write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    c.post("/demo/reset")
    for persona, focus in FOCUS.items():
        t = c.post("/demo/session", json={"persona": persona}).json()["token"]
        h = {"Authorization": f"Bearer {t}"}
        save(persona, "me_map", c.get("/me/map", headers=h).json())
        save(persona, "me_focus", c.post("/me/focus", headers=h, json=focus).json())
        save(persona, "me_focus_crisis", c.post("/me/focus", headers=h, json={**focus, "text": "I want to end my life"}).json())
        nxt = c.get("/me/next", headers=h).json()
        save(persona, "me_next", nxt)
        save(persona, "me_card", c.get("/me/card", headers=h).json())
        save(persona, "pulse", c.get("/pulse", headers=h).json())
        save(persona, "win_crisis", c.post("/wins", headers=h, json={"text": "I want to end my life"}).json())
        save(persona, "same_here", c.post("/wins/w01/same-here", headers=h).json())
        cm = c.post("/commitments", headers=h, json={"rec_id": nxt["pick"]["rec_id"]}).json()
        save(persona, "commitment", cm)
        if persona == "andre":
            save("_shared", "invite", c.get(f"/invites/{cm['invite_token']}").json())
            save("_shared", "invite_accepted", c.post(f"/invites/{cm['invite_token']}").json())
        sk = c.post("/demo/skip-ahead", headers=h, json={"to": "next_due"}).json()
        save(persona, "skip_ahead", sk)
        c.post("/demo/skip-ahead", headers=h, json={"to": "next_due"})
        fu = c.post(f"/followups/{cm['commitment_id']}", headers=h, json={"went": True, "helped": 4})
        if fu.status_code == 200:
            save(persona, "followup", fu.json())
        save(persona, "me_memory", c.get("/me/memory", headers=h).json())
        save(persona, "me_inbox", c.get("/me/inbox", headers=h).json())
        alt = nxt["alternates"][0]["rec_id"] if nxt["alternates"] else nxt["pick"]["rec_id"]
        save(persona, "me_next_after_decline", c.post(f"/me/next/{alt}/decline", headers=h, json={"reason": "swap"}).json())
        save(persona, "win_accepted", c.post("/wins", headers=h, json={"text": "Took a walk between classes today. Felt good."}).json())
        print("recorded", persona)
    t = c.post("/demo/session", json={"persona": "staff"}).json()["token"]
    h = {"Authorization": f"Bearer {t}"}
    for key, path in (("staff_funnel", "/staff/funnel"), ("staff_gaps", "/staff/gaps"), ("staff_weekly", "/staff/weekly?campus=new_brunswick"),
                      ("staff_dips", "/staff/dips"), ("staff_retakes", "/staff/retakes")):
        save("staff", key, c.get(path, headers=h).json())
    save("_shared", "personas", c.get("/demo/personas").json())
    c.post("/demo/reset")
    print("recorded staff; reset done")


if __name__ == "__main__":
    main()
