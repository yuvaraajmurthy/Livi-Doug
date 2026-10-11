"""Voice with the voice_bot.py port: Nova 2.5 Sonic in us-east-1, guardrail rules in the prompt, knowledge base and
email tools (boto3 mocked; the real sendText Lambda is never invoked)."""
import json

from tests.voice.test_voice_ws import _frames, _token, fake  # noqa: F401  (fake is a fixture)

GUARDRAIL = {"blockedInputMessaging": "Blocked by Rutgers policy.",
             "topicPolicy": {"topics": [{"name": "Medical advice", "definition": "Diagnosing or prescribing."}]}}


def test_voice_model_is_nova_2_5_sonic_in_us_east_1():
    from app.voice_ws.session import make_agent
    model = make_agent("hi", []).model
    assert model.region == "us-east-1"
    assert model.get_config()["model_id"] == "amazon.nova-2-5-sonic"
    audio = model.get_audio_config()
    assert audio["input"]["sample_rate"] == 16000 and audio["output"]["sample_rate"] == 24000


def test_voice_gets_guardrail_rules_and_can_search_kb_and_email(client, fake, fake_aws, bedrock_on):
    fake_aws("bedrock", get_guardrail=GUARDRAIL)
    kb = fake_aws("bedrock-agent-runtime", retrieve={"retrievalResults": [{"content": {"text": "Rooms on floor 2."}}]})
    lam = fake_aws("lambda", invoke={"StatusCode": 200})
    box = fake([
        {"type": "bidi_transcript_block", "role": "user", "transcript": "where can I study? email it to me"},
        {"type": "call_tool", "name": "search_knowledge_base", "input": {"query": "library study rooms"}},
        {"type": "call_tool", "name": "send_email_notification", "input": {"subject": "Study rooms", "message": "Floor 2."}},
        {"type": "bidi_transcript_block", "role": "assistant", "transcript": "Floor two. I emailed it to you."},
    ])
    with client.websocket_connect("/voice/ws") as ws:
        ws.send_json({"type": "start", "token": _token(client)})
        assert ws.receive_json()["type"] == "ready"
        _frames(ws, {"end"})
    assert "ACTIVE BEDROCK GUARDRAIL RULES:" in box["prompt"] and "1. Medical advice" in box["prompt"]
    assert "spoken" in box["prompt"].lower()
    assert {"search_knowledge_base", "send_email_notification", "search_events"} <= set(box["agent"].tools)
    assert kb.calls[0][1]["retrievalQuery"] == {"text": "library study rooms"}
    (op, kw), = lam.calls
    assert json.loads(kw["Payload"]) == {"subject": "Study rooms", "message": "Floor 2."}
