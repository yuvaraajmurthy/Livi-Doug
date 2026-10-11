"""Scheduling through the AI (chat and voice) must land in the same server state as the card's "Remind me":
a planned commitment for the session's student, a reminder + follow-up notification, and the reminder firing into
the inbox on skip-ahead. The tool never fails silently: anything not saved is said so to the model."""
from tests.chat.test_chat import FOCUS, LUNCH, _session, _sse, scripted  # noqa: F401  (scripted is a fixture)
from tests.voice.test_voice_ws import _frames, fake  # noqa: F401  (fake is a fixture)


def _tools(token: str):
    from app import auth, clock
    from app.chat import prompt
    from app.chat.tools import ToolContext, make_tools
    from app.db import conn
    ctx = auth.parse(token)
    with conn() as c:
        now = clock.now(c, ctx.sid)
        bundle = prompt.build(c, ctx, now)
    emitted: list[dict] = []
    tc = ToolContext(ctx=ctx, bundle=bundle, now=now, emit=emitted.append)
    return {t.tool_name: t for t in make_tools(tc)}, tc, emitted


def test_chat_reminder_is_planned_scheduled_and_fires_into_the_inbox(client, db, scripted):  # noqa: F811
    scripted([[{"tool": "set_reminder", "input": {"event_id": LUNCH}}], [{"text": "Done, it's on your plan."}]])
    s, h = _session(client)
    client.post("/me/focus", json=FOCUS, headers=h)
    events = _sse(client.post("/chat", json={"message": "yes, put the lunch on my schedule"}, headers=h))
    plan = next(d for e, d in events if e == "plan")
    cm = db.execute("SELECT * FROM commitments WHERE id = %s", (plan["commitment_id"],)).fetchone()
    assert cm["student_id"] == s["student_id"] and cm["status"] == "planned" and cm["item_id"] == LUNCH
    notes = db.execute("SELECT kind, deep_link, status FROM notifications WHERE commitment_id = %s", (cm["id"],)).fetchall()
    assert {n["kind"] for n in notes} == {"reminder", "followup"} and all(n["status"] == "scheduled" for n in notes)
    # the card's Remind me on the same event sees the same plan
    assert client.post(f"/items/{LUNCH}/remind", headers=h).json()["commitment_id"] == cm["id"]
    fired = client.post("/demo/skip-ahead", json={"to": "2026-10-13T12:20:00-04:00"}, headers=h).json()["fired"]
    assert any(f["kind"] == "reminder" and f["commitment_id"] == cm["id"] for f in fired)
    inbox = client.get("/me/inbox", headers=h).json()["items"]
    assert any(i["kind"] == "reminder" and i["deep_link"] == f"/plan/{cm['id']}" for i in inbox)


def test_set_reminder_accepts_a_real_id_from_an_earlier_turn_and_rejects_invented_ones(client, db):
    s, _ = _session(client)
    tools, tc, emitted = _tools(s["token"])
    tc.bundle.catalog_ids.discard(LUNCH)  # e.g. found by search_events in an earlier turn (tc.found is per turn)
    out = tools["set_reminder"](event_id=LUNCH)
    assert "reminder set" in out.lower(), out
    assert emitted[-1]["type"] == "plan" and emitted[-1]["plan"]["item"]["id"] == LUNCH
    n = len(emitted)
    assert "nothing was saved" in tools["set_reminder"](event_id="made-up-event").lower()
    assert len(emitted) == n


def test_set_reminder_resolves_an_exact_title(client, db):
    s, _ = _session(client)
    tools, tc, emitted = _tools(s["token"])
    titles: dict[str, list[str]] = {}
    for i, it in tc.bundle.items.items():
        titles.setdefault(it.title.replace(" (sample)", ""), []).append(i)
    title, ids = next((t, v) for t, v in titles.items() if len(v) == 1 and tc.bundle.items[v[0]].starts_at)
    out = tools["set_reminder"](event_id=title)
    assert "saved to the student's plan" in out.lower(), out
    assert emitted[-1]["plan"]["item"]["id"] == ids[0]


def test_set_reminder_on_a_started_event_says_so_and_leaves_nothing_behind(client, db):
    s, h = _session(client)
    client.post("/demo/skip-ahead", json={"to": "2026-10-13T12:40:00-04:00"}, headers=h)
    tools, _, emitted = _tools(s["token"])
    out = tools["set_reminder"](event_id=LUNCH)
    assert "already started" in out and not emitted
    for table in ("commitments", "recommendations"):
        n = db.execute(f"SELECT count(*) AS n FROM {table} WHERE student_id = %s AND item_id = %s",
                       (s["student_id"], LUNCH)).fetchone()["n"]
        assert n == 0, table


def test_voice_set_reminder_puts_the_plan_on_screen_and_in_the_history(client, db, fake):  # noqa: F811
    fake([
        {"type": "bidi_transcript_block", "role": "user", "transcript": "yes remind me about the lunch"},
        {"type": "call_tool", "name": "set_reminder", "input": {"event_id": LUNCH}},
        {"type": "bidi_transcript_block", "role": "assistant", "transcript": "Done, I'll remind you Tuesday."},
    ])
    s, h = _session(client)
    with client.websocket_connect("/voice/ws") as ws:
        ws.send_json({"type": "start", "token": s["token"]})
        assert ws.receive_json()["type"] == "ready"
        frames = _frames(ws, {"end"})
    ui = next(f["event"] for f in frames if f["type"] == "ui")
    assert ui["type"] == "plan" and ui["plan"]["item"]["id"] == LUNCH and ui["plan"]["reminder_at"]
    cm = db.execute("SELECT student_id, reminder_at FROM commitments WHERE id = %s", (ui["plan"]["commitment_id"],)).fetchone()
    assert cm["student_id"] == s["student_id"] and cm["reminder_at"]
    hist = client.get("/chat/history", headers=h).json()["messages"]
    assert hist[-1]["blocks"][0]["type"] == "plan"
