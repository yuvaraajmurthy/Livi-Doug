"""Voice WebSocket plumbing with a fake bidirectional agent (no Bedrock, no audio hardware)."""
import asyncio
import base64

import pytest

LUNCH = "pin-andre-lunch-2026-10-13"


class FakeAgent:
    """Duck-typed BidiAgent: records what it was sent, plays a script of output events."""
    def __init__(self, script, tools):
        self.script = list(script)
        self.tools = {t.tool_name: t for t in tools}
        self.sent = []
        self.started = self.stopped = False

    async def start(self, invocation_state=None):
        self.started = True

    async def send(self, data):
        self.sent.append(data)

    async def receive(self):
        await asyncio.sleep(0.05)
        for ev in self.script:
            if ev.get("type") == "call_tool":
                self.tools[ev["name"]](**ev["input"])
                await asyncio.sleep(0.05)
                continue
            yield ev
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.3)

    async def stop(self):
        self.stopped = True


@pytest.fixture
def fake(monkeypatch):
    box = {}

    def use(script):
        def make(system_prompt, tools):
            box["agent"] = FakeAgent(script, tools)
            box["prompt"] = system_prompt
            return box["agent"]
        monkeypatch.setattr("app.voice_ws.session.make_agent", make)
        monkeypatch.setattr("app.voice_ws.session.audio_input", lambda pcm: {"audio_delta": pcm})
        return box
    return use


def _token(client):
    return client.post("/demo/session", json={"persona": "andre", "sandbox": True}).json()["token"]


def _frames(ws, until: set[str], limit=60):
    got = []
    for _ in range(limit):
        f = ws.receive_json()
        got.append(f)
        if f["type"] in until:
            break
    return got


def test_requires_a_student_token(client):
    with client.websocket_connect("/voice/ws") as ws:
        ws.send_json({"type": "start", "token": "nope"})
        assert ws.receive_json()["type"] == "error"


def test_audio_in_and_audio_transcripts_cards_out(client, fake):
    box = fake([
        {"type": "bidi_transcript_block", "role": "user", "transcript": "anything social this week?"},
        {"type": "call_tool", "name": "show_events", "input": {"event_ids": [LUNCH], "why": "fits"}},
        {"type": "bidi_audio_delta", "audio": base64.b64encode(b"\x00\x01" * 10).decode()},
        {"type": "bidi_transcript_block", "role": "assistant", "transcript": "I put the lunch on your screen."},
    ])
    with client.websocket_connect("/voice/ws") as ws:
        ws.send_json({"type": "start", "token": _token(client)})
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "audio", "data": base64.b64encode(b"\x01\x02" * 320).decode()})
        frames = _frames(ws, {"end"})
    kinds = [f["type"] for f in frames]
    assert "audio" in kinds
    ui = next(f for f in frames if f["type"] == "ui")
    assert ui["event"]["type"] == "events" and ui["event"]["items"][0]["id"] == LUNCH
    finals = [f for f in frames if f["type"] == "transcript" and f["final"]]
    assert [f["role"] for f in finals] == ["user", "assistant"]
    assert any(isinstance(x, dict) and "audio_delta" in x for x in box["agent"].sent)
    assert "spoken" in box["prompt"].lower()
    assert box["agent"].stopped


def test_crisis_transcript_ends_with_crisis_card(client, fake, db):
    fake([{"type": "bidi_transcript_block", "role": "user", "transcript": "I want to kill myself"}])
    with client.websocket_connect("/voice/ws") as ws:
        ws.send_json({"type": "start", "token": _token(client)})
        assert ws.receive_json()["type"] == "ready"
        frames = _frames(ws, {"end"})
    crisis = next(f for f in frames if f["type"] == "crisis")
    assert crisis["lines"] and crisis["title"]
    assert not any(f["type"] == "transcript" and "kill" in f.get("text", "") for f in frames)


def test_voice_turns_join_the_chat_history(client, fake):
    fake([
        {"type": "bidi_transcript_block", "role": "user", "transcript": "what's on tomorrow?"},
        {"type": "bidi_transcript_block", "role": "assistant", "transcript": "A lunch at Robeson."},
    ])
    tok = _token(client)
    with client.websocket_connect("/voice/ws") as ws:
        ws.send_json({"type": "start", "token": tok})
        ws.receive_json()
        _frames(ws, {"end"})
    hist = client.get("/chat/history", headers={"Authorization": f"Bearer {tok}"}).json()
    assert [m["text"] for m in hist["messages"]] == ["what's on tomorrow?", "A lunch at Robeson."]
