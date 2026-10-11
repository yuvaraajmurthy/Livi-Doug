"""Chat with the voice_bot.py port (live DB, scripted model, boto3 mocked): guardrail rules in the prompt, knowledge
base and email tools in a real chat turn. The real sendText Lambda is never invoked."""
import json

from tests.chat.test_chat import _session, _sse, scripted  # noqa: F401  (scripted is a fixture)

GUARDRAIL = {"blockedInputMessaging": "Blocked by Rutgers policy.",
             "topicPolicy": {"topics": [{"name": "Medical advice", "definition": "Diagnosing or prescribing."}]}}


def test_prompt_has_guardrail_rules_and_kb_email_rules_before_the_catalog(client, db, fake_aws, bedrock_on):
    from app import clock
    from app.auth import parse
    from app.chat import assist_aws, prompt
    fake_aws("bedrock", get_guardrail=GUARDRAIL)
    s, _ = _session(client)
    for style in ("chat", "voice"):
        system = prompt.build(db, parse(s["token"]), clock.default_now(), style=style).system
        rules = system.index("ACTIVE BEDROCK GUARDRAIL RULES:")
        assert "1. Medical advice: Diagnosing or prescribing." in system
        assert 'decline immediately with: "Blocked by Rutgers policy."' in system
        assert system.index(prompt.TOOLS) < system.index(assist_aws.TOOL_INSTRUCTIONS) < rules
        assert rules < system.index("Event catalog")
        assert system.startswith(prompt.ROLE)                                   # Compass role kept


def test_chat_turn_searches_kb_and_emails_a_summary(client, db, scripted, fake_aws):
    kb = fake_aws("bedrock-agent-runtime", retrieve={"retrievalResults": [
        {"content": {"text": "Alexander Library group study rooms can be booked online."}}]})
    lam = fake_aws("lambda", invoke={"StatusCode": 200})
    m = scripted([
        [{"tool": "search_knowledge_base", "input": {"query": "library study rooms"}}],
        [{"tool": "send_email_notification",
          "input": {"subject": "Library study rooms", "message": "Alexander Library group study rooms can be booked online."}}],
        [{"text": "Alexander Library has bookable group rooms. I emailed you the details."}],
    ])
    s, h = _session(client)
    events = _sse(client.post("/chat", json={"message": "where can I book a study room? email me the info"}, headers=h))
    statuses = [d["text"] for e, d in events if e == "status"]
    assert "Checking Rutgers info…" in statuses and "Sending the email…" in statuses
    assert kb.calls[0][1] == {"knowledgeBaseId": "DQTTJ5HDWT", "retrievalQuery": {"text": "library study rooms"}}
    (op, kw), = lam.calls
    assert kw["FunctionName"].endswith(":function:sendText") and kw["InvocationType"] == "RequestResponse"
    assert json.loads(kw["Payload"]) == {"subject": "Library study rooms",
                                         "message": "Alexander Library group study rooms can be booked online."}
    results = json.dumps(m.calls[2]["messages"])
    assert "Alexander Library group study rooms" in results and "Email sent successfully." in results
    assert {"search_events", "search_knowledge_base", "send_email_notification"} <= set(m.calls[0]["tools"])
    assert next(d for e, d in events if e == "done")["source"] == "ai"
