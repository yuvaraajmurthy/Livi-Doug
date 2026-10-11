"""X-Compass-Trace: numbers-only evidence of what the backend did, for the stage demo's proof panels."""


def _h(client, persona="andre"):
    t = client.post("/demo/session", json={"persona": persona, "sandbox": True}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def _trace(r):
    raw = r.headers.get("X-Compass-Trace", "")
    return dict(p.split("=", 1) for p in raw.split(";") if p)


FOCUS = {"dimension": "social", "barriers": ["no_time", "dont_know_anyone"]}


def test_next_has_rank_trace(client):
    h = _h(client)
    client.post("/me/focus", json=FOCUS, headers=h)
    tr = _trace(client.get("/me/next", headers=h))
    assert int(tr["candidates"]) >= int(tr["passed"]) > 0
    assert float(tr["rank_ms"]) >= 0
    assert tr["wording"] in {"ai", "template"}


def test_focus_crisis_trace_says_lexicon(client):
    h = _h(client)
    r = client.post("/me/focus", json={**FOCUS, "text": "i want to kill myself"}, headers=h)
    assert r.json()["kind"] == "crisis"
    tr = _trace(r)
    assert tr["safety"] == "lexicon"
    assert float(tr["safety_ms"]) >= 0


def test_ask_crisis_trace_says_lexicon(client):
    r = client.post("/ask", json={"question": "I don't want to be here anymore"}, headers=_h(client))
    assert r.json()["kind"] == "crisis"
    assert _trace(r)["safety"] == "lexicon"


def test_trace_values_are_never_free_text(client):
    h = _h(client)
    r = client.post("/me/focus", json={**FOCUS, "text": "my calc homework keeps me up"}, headers=h)
    raw = r.headers.get("X-Compass-Trace", "")
    assert "calc" not in raw and " " not in raw


def test_trace_exposed_to_browsers(client):
    r = client.get("/health", headers={"Origin": "https://x.example"})
    assert "x-compass-trace" in r.headers.get("access-control-expose-headers", "").lower()
