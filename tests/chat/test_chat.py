"""Chat backend (spec 2026-10-11 §3): catalog, prompt, memory, tools, SSE turn, fallback, items API."""
import json

import pytest

from tests.chat.fakes import ScriptedModel

FOCUS = {"dimension": "social", "barriers": ["no_time", "dont_know_anyone"]}
LUNCH = "pin-andre-lunch-2026-10-13"


def _session(client, persona="andre"):
    s = client.post("/demo/session", json={"persona": persona, "sandbox": True}).json()
    return s, {"Authorization": f"Bearer {s['token']}"}


def _sse(resp) -> list[tuple[str, dict]]:
    out, ev = [], None
    for line in resp.text.splitlines():
        if line.startswith("event: "):
            ev = line[7:]
        elif line.startswith("data: ") and ev:
            out.append((ev, json.loads(line[6:])))
            ev = None
    return out


@pytest.fixture
def scripted(monkeypatch):
    holder = {}

    def use(turns):
        m = ScriptedModel(turns)
        holder["m"] = m
        monkeypatch.setattr("app.chat.agent.make_model", lambda style="chat": m)
        monkeypatch.setattr("app.chat.agent.models_available", lambda: True)
        return m
    return use


# ------------------------------------------------------------------------------------------------ catalog + prompt
def test_catalog_lines_are_compact_and_capped(client, db):
    from app.chat import catalog
    from app.repo import kb
    from app import clock
    s, _ = _session(client)
    now = clock.default_now()
    sctx = kb.student_ctx(db, s["student_id"], now, False)
    items = catalog.build(db, sctx, now)
    assert 0 < len(items) <= catalog.MAX_ROWS
    text = catalog.render(items)
    line = next(l for l in text.splitlines() if l.startswith(LUNCH))
    assert line.count(" | ") == 5
    assert "Tue Oct 13" in line and "Paul Robeson Campus Center" in line and "free" in line


def test_prompt_has_snapshot_catalog_and_caps(client, db):
    from app.chat import prompt
    from app import clock
    from app.auth import parse
    s, _ = _session(client)
    bundle = prompt.build(db, parse(s["token"]), clock.default_now())
    assert LUNCH in bundle.catalog_ids
    assert LUNCH in bundle.system
    assert "Monday" in bundle.system and "Newark" in bundle.system
    assert len(bundle.profile) <= prompt.PROFILE_CAP and len(bundle.memory) <= prompt.MEMORY_CAP
    voice = prompt.build(db, parse(s["token"]), clock.default_now(), style="voice")
    assert voice.system != bundle.system and "spoken" in voice.system.lower()


# ------------------------------------------------------------------------------------------------ memory
def test_remember_refuses_crisis_and_health_text(client, db):
    from app.chat import memory
    s, _ = _session(client)
    assert isinstance(memory.remember(db, s["student_id"], "constraint", "I want to kill myself"), memory.Refused)
    assert isinstance(memory.remember(db, s["student_id"], "constraint", "I take sertraline every morning"), memory.Refused)


def test_remember_supersedes_same_key_and_keeps_history(client, db):
    from app.chat import memory
    s, _ = _session(client)
    a = memory.remember(db, s["student_id"], "time_works", "Fridays after 3 are free")
    b = memory.remember(db, s["student_id"], "time_works", "Fridays after 3 are free for me now")
    assert not isinstance(a, memory.Refused) and not isinstance(b, memory.Refused)
    rows = db.execute("SELECT statement, source_ref FROM student_memory WHERE student_id = %s AND kind = 'time_works'",
                      (s["student_id"],)).fetchall()
    assert len(rows) == 1 and rows[0]["statement"] == "Fridays after 3 are free for me now"
    assert rows[0]["source_ref"]["history"][0]["statement"] == "Fridays after 3 are free"


def test_remember_caps_active_chat_facts(client, db):
    from app.chat import memory
    s, _ = _session(client)
    for i in range(memory.CAP + 3):
        memory.remember(db, s["student_id"], "interest", f"Likes hobby number {i} a lot")
    n = db.execute("SELECT count(*) AS n FROM student_memory WHERE student_id = %s AND source_type = 'your_words'",
                   (s["student_id"],)).fetchone()["n"]
    assert n <= memory.CAP


# ------------------------------------------------------------------------------------------------ chat turns
def test_crisis_message_never_reaches_a_model_and_is_not_stored(client, db, scripted):
    m = scripted([[{"text": "should not run"}]])
    s, h = _session(client)
    events = _sse(client.post("/chat", json={"message": "honestly I want to kill myself"}, headers=h))
    assert [e for e, _ in events if e not in ("meta",)] == ["crisis", "done"]
    assert m.calls == []
    n = db.execute("SELECT count(*) AS n FROM chat_messages WHERE student_id = %s", (s["student_id"],)).fetchone()["n"]
    assert n == 0


def test_agent_turn_shows_events_as_buttons_and_streams_text(client, db, scripted):
    m = scripted([
        [{"tool": "show_events", "input": {"event_ids": [LUNCH, "not-a-real-id"], "why": "fits his gap"}}],
        [{"text": "This lunch sits right in your Tuesday gap and it's free."}],
    ])
    s, h = _session(client)
    events = _sse(client.post("/chat", json={"message": "anything social with free food this week?"}, headers=h))
    kinds = [e for e, _ in events]
    assert kinds[0] == "meta" and kinds[-1] == "done"
    shown = next(d for e, d in events if e == "events")
    assert [i["id"] for i in shown["items"]] == [LUNCH]          # unknown id dropped
    assert shown["items"][0]["when_label"].startswith("Tue Oct 13")
    assert "status" in kinds
    text = "".join(d["text"] for e, d in events if e == "delta")
    assert "Tuesday gap" in text
    assert LUNCH in m.calls[0]["system_prompt"]
    hist = client.get("/chat/history", headers=h).json()
    assert [x["role"] for x in hist["messages"]] == ["user", "assistant"]
    assert hist["messages"][1]["blocks"][0]["type"] == "events"


def test_remember_tool_emits_memory_and_it_shows_in_you(client, db, scripted):
    scripted([
        [{"tool": "remember", "input": {"fact": "Plays pickup basketball", "kind": "interest"}}],
        [{"text": "Noted."}],
    ])
    s, h = _session(client)
    events = _sse(client.post("/chat", json={"message": "I play basketball most weeks"}, headers=h))
    mem = next(d for e, d in events if e == "memory")
    assert mem["statement"] == "Plays pickup basketball"
    items = client.get("/me/memory", headers=h).json()["items"]
    row = next(i for i in items if i["id"] == mem["id"])
    assert row["source"]["label"].startswith("You said in chat")


def test_set_reminder_tool_creates_a_plan(client, db, scripted):
    scripted([[{"tool": "set_reminder", "input": {"event_id": LUNCH}}], [{"text": "Done, I'll remind you."}]])
    s, h = _session(client)
    client.post("/me/focus", json=FOCUS, headers=h)
    events = _sse(client.post("/chat", json={"message": "yes remind me about the lunch"}, headers=h))
    plan = next(d for e, d in events if e == "plan")
    assert plan["item"]["id"] == LUNCH and plan["reminder_at"]


def test_fallback_when_models_are_off(client, db):
    s, h = _session(client)
    events = _sse(client.post("/chat", json={"message": "board games lunch"}, headers=h))
    done = next(d for e, d in events if e == "done")
    assert done["source"] == "fallback"
    assert any(e == "delta" for e, _ in events)


def test_new_chat_starts_a_fresh_conversation(client, db, scripted):
    scripted([[{"text": "Hi."}]])
    s, h = _session(client)
    first = _sse(client.post("/chat", json={"message": "hello there"}, headers=h))
    conv = next(d for e, d in first if e == "meta")["conversation_id"]
    new = client.post("/chat/new", headers=h).json()["conversation_id"]
    assert new != conv
    assert client.get("/chat/history", headers=h).json()["messages"] == []


# ------------------------------------------------------------------------------------------------ items API
def test_item_detail_has_map_and_actions(client):
    s, h = _session(client)
    d = client.get(f"/items/{LUNCH}", headers=h).json()
    assert d["title"].startswith("Commuter lunch") and d["lat"] and d["lon"]
    assert d["directions_url"].startswith("https://www.google.com/maps")
    assert d["when_label"].startswith("Tue Oct 13") and d["cost_label"] == "Free"
    assert d["source"]["name"]
    assert client.get("/items/nope", headers=h).status_code == 404


def test_remind_is_idempotent(client, db):
    s, h = _session(client)
    a = client.post(f"/items/{LUNCH}/remind", headers=h).json()
    b = client.post(f"/items/{LUNCH}/remind", headers=h).json()
    assert a["commitment_id"] == b["commitment_id"] and a["reminder_at"]
