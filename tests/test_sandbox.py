"""Sandbox sessions: each table-mode tour gets its own copy of the persona, invisible to staff and wiped by reset."""


def _session(client, persona, sandbox):
    r = client.post("/demo/session", json={"persona": persona, "sandbox": sandbox})
    assert r.status_code == 200, r.text
    return r.json()


def _h(s):
    return {"Authorization": f"Bearer {s['token']}"}


FOCUS = {"dimension": "social", "barriers": ["no_time", "dont_know_anyone"]}


def test_sandbox_gets_clone_id(client):
    s = _session(client, "andre", True)
    assert s["student_id"].startswith("DEMO-ANDRE~")


def test_plain_session_keeps_base_id(client):
    assert _session(client, "andre", False)["student_id"] == "DEMO-ANDRE"


def test_sandbox_isolation(client):
    a, b = _session(client, "andre", True), _session(client, "andre", True)
    client.post("/me/focus", json=FOCUS, headers=_h(a))
    assert client.get("/me/map", headers=_h(a)).json()["profile"]["focus"] == "social"
    assert client.get("/me/map", headers=_h(b)).json()["profile"]["focus"] is None
    base = _session(client, "andre", False)
    assert client.get("/me/map", headers=_h(base)).json()["profile"]["focus"] is None


def test_sandbox_has_scores_and_story(client):
    s = _session(client, "andre", True)
    m = client.get("/me/map", headers=_h(s)).json()
    assert m["latest"]["scores"]["social"] == 1.9
    client.post("/me/focus", json=FOCUS, headers=_h(s))
    nxt = client.get("/me/next", headers=_h(s)).json()
    assert nxt["pick"]["item"]["id"] == "pin-andre-lunch-2026-10-13"


def test_staff_excludes_sandbox(client, staff_headers):
    before = client.get("/staff/funnel", headers=staff_headers).json()["rows"]
    s = _session(client, "andre", True)
    client.post("/me/focus", json=FOCUS, headers=_h(s))
    client.get("/me/next", headers=_h(s))
    after = client.get("/staff/funnel", headers=staff_headers).json()["rows"]
    assert before == after


def test_reset_removes_sandboxes(client, db):
    _session(client, "andre", True)
    assert client.post("/demo/reset").status_code == 200
    assert db.execute("SELECT count(*) AS n FROM students WHERE id LIKE '%%~%%'").fetchone()["n"] == 0


def test_dispatcher_tick_sweeps_old_sandboxes(client, db):
    s = _session(client, "andre", True)
    db.execute("UPDATE students SET sandbox_created = now() - interval '7 hours' WHERE id = %s", (s["student_id"],))
    fresh = _session(client, "andre", True)
    from app.loop.notify import tick
    tick()
    ids = {r["id"] for r in db.execute("SELECT id FROM students WHERE sandbox").fetchall()}
    assert s["student_id"] not in ids
    assert fresh["student_id"] in ids


def test_sandbox_commitments_do_not_inflate_social_proof(client):
    def going():
        s = _session(client, "andre", True)
        client.post("/me/focus", json=FOCUS, headers=_h(s))
        return client.get("/me/next", headers=_h(s)).json()["pick"]["going"]["count"], s

    before, s = going()
    rec = client.get("/me/next", headers=_h(s)).json()["pick"]["rec_id"]
    assert client.post("/commitments", json={"rec_id": rec}, headers=_h(s)).status_code == 200
    after, _ = going()
    assert after == before
