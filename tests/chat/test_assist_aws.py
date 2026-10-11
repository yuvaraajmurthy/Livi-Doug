"""voice_bot.py port (no database, boto3 mocked): settings, guardrail-as-prompt rules, knowledge base and email tools.
The real sendText Lambda emails a real person; nothing here (or anywhere in tests) may invoke it."""
import json

from app.chat import assist_aws

GUARDRAIL = {
    "blockedInputMessaging": "Sorry, I can't help with that. Please contact Rutgers student services.",
    "topicPolicy": {"topics": [
        {"name": "Medical advice", "definition": "Diagnosing conditions or recommending medication.", "type": "DENY"},
        {"name": "Academic dishonesty", "definition": "Writing graded work for the student.", "type": "DENY"},
    ]},
}


# ------------------------------------------------------------------------------------------------ settings
def test_settings_defaults_match_the_tested_env():
    from config.settings import Settings
    s = Settings(_env_file=None)
    assert s.assistant_region == "us-east-1"
    assert s.bedrock_guardrail_id == "7a6u58w100yu" and s.bedrock_guardrail_version == "DRAFT"
    assert s.bedrock_knowledge_base_id == "DQTTJ5HDWT"
    assert s.send_text_lambda_arn == "arn:aws:lambda:us-east-1:204762614174:function:sendText"
    assert s.model_fast == "us.anthropic.claude-haiku-4-5-20251001-v1:0" and s.model_voice == "amazon.nova-2-5-sonic"


def test_settings_are_env_overridable(monkeypatch):
    from config.settings import Settings
    monkeypatch.setenv("BEDROCK_GUARDRAIL_ID", "gr-x")
    monkeypatch.setenv("BEDROCK_KNOWLEDGE_BASE_ID", "KB-X")
    monkeypatch.setenv("ASSISTANT_REGION", "us-east-2")
    s = Settings(_env_file=None)
    assert (s.bedrock_guardrail_id, s.bedrock_knowledge_base_id, s.assistant_region) == ("gr-x", "KB-X", "us-east-2")


# ------------------------------------------------------------------------------------------------ guardrail
def test_guardrail_rules_text_from_bedrock(fake_aws):
    br = fake_aws("bedrock", get_guardrail=GUARDRAIL)
    text = assist_aws.load_guardrail_from_bedrock("7a6u58w100yu", "DRAFT")
    assert br.calls == [("get_guardrail", {"guardrailIdentifier": "7a6u58w100yu", "guardrailVersion": "DRAFT"})]
    assert ("bedrock", "us-east-1") in fake_aws.regions
    assert text == (
        "ACTIVE BEDROCK GUARDRAIL RULES:\n"
        "You must follow the active Amazon Bedrock Guardrail policies below.\n"
        "Never provide answers for the following restricted topics:\n"
        "1. Medical advice: Diagnosing conditions or recommending medication.\n"
        "2. Academic dishonesty: Writing graded work for the student.\n\n"
        'If any restricted topic or sensitive PII is mentioned, decline immediately with: '
        '"Sorry, I can\'t help with that. Please contact Rutgers student services."\n'
    )


def test_guardrail_default_blocked_message(fake_aws):
    fake_aws("bedrock", get_guardrail={"topicPolicy": {"topics": []}})
    text = assist_aws.load_guardrail_from_bedrock("g", "DRAFT")
    assert text.endswith('decline immediately with: "I cannot fulfill this request. '
                         'Please contact campus student services directly."\n')


def test_guardrail_fetch_failure_uses_voice_bot_fallback(fake_aws):
    fake_aws("bedrock", get_guardrail=RuntimeError("AccessDenied"))
    assert assist_aws.load_guardrail_from_bedrock("g", "DRAFT") == assist_aws.FALLBACK
    assert assist_aws.FALLBACK.startswith("You are the Rutgers student assistant voice agent. ")


def test_guardrail_is_cached_between_turns(fake_aws, bedrock_on):
    br = fake_aws("bedrock", get_guardrail=GUARDRAIL)
    a = assist_aws.guardrail_rules()
    b = assist_aws.guardrail_rules()
    assert a == b and "1. Medical advice" in a
    assert len(br.calls) == 1


def test_failed_guardrail_fetch_is_retried_after_the_short_ttl(fake_aws, bedrock_on, monkeypatch):
    br = fake_aws("bedrock", get_guardrail=RuntimeError("down"))
    assert assist_aws.guardrail_rules() == assist_aws.FALLBACK
    br.responses["get_guardrail"] = GUARDRAIL
    assert assist_aws.guardrail_rules() == assist_aws.FALLBACK            # still cached
    t = assist_aws.time.monotonic() + assist_aws.GUARDRAIL_FAIL_TTL_S + 1
    monkeypatch.setattr(assist_aws.time, "monotonic", lambda: t)
    assert "ACTIVE BEDROCK GUARDRAIL RULES" in assist_aws.guardrail_rules()
    assert len(br.calls) == 2


def test_no_guardrail_fetch_when_bedrock_is_off(fake_aws, monkeypatch):
    from config.settings import get_settings
    monkeypatch.setattr(get_settings(), "bedrock_enabled", False)
    br = fake_aws("bedrock", get_guardrail=GUARDRAIL)
    assert assist_aws.guardrail_rules() == assist_aws.FALLBACK
    assert br.calls == []


def test_prompt_assistant_sections_are_kb_email_rules_then_guardrail(fake_aws, bedrock_on):
    from app.chat import prompt
    fake_aws("bedrock", get_guardrail=GUARDRAIL)
    tools_text, rules = prompt.assistant_sections()
    assert "search_knowledge_base tool to look up library spaces" in tools_text
    assert "invoke the send_email_notification tool" in tools_text and "notified by email" in tools_text
    assert rules.startswith("ACTIVE BEDROCK GUARDRAIL RULES:")
    assert "search_knowledge_base" in prompt.TOOLS and "send_email_notification" in prompt.TOOLS


# ------------------------------------------------------------------------------------------------ knowledge base
def test_kb_joins_result_texts(fake_aws):
    kb = fake_aws("bedrock-agent-runtime", retrieve={"retrievalResults": [
        {"content": {"text": "Alexander Library has group study rooms."}},
        {"content": {"text": "Book rooms up to 7 days ahead."}},
        {"content": {}},
    ]})
    out = assist_aws.search_knowledge_base("library study rooms")
    assert out == "Alexander Library has group study rooms.\n\nBook rooms up to 7 days ahead.\n\n"
    assert kb.calls == [("retrieve", {"knowledgeBaseId": "DQTTJ5HDWT", "retrievalQuery": {"text": "library study rooms"}})]
    assert ("bedrock-agent-runtime", "us-east-1") in fake_aws.regions


def test_kb_no_results_and_errors(fake_aws):
    kb = fake_aws("bedrock-agent-runtime", retrieve={"retrievalResults": []})
    assert assist_aws.search_knowledge_base("x") == "No matching information found in knowledge base."
    kb.responses["retrieve"] = RuntimeError("boom")
    assert assist_aws.search_knowledge_base("x") == "Could not retrieve from knowledge base: boom"


# ------------------------------------------------------------------------------------------------ email (mocked)
def test_email_invokes_send_text_lambda_with_subject_and_message(fake_aws):
    lam = fake_aws("lambda", invoke={"StatusCode": 200})
    out = assist_aws.send_email_notification("Your reminder", "Commuter lunch, Tue Oct 13, 12:30, Robeson.")
    assert out == "Email sent successfully."
    (op, kw), = lam.calls
    assert op == "invoke"
    assert kw["FunctionName"] == "arn:aws:lambda:us-east-1:204762614174:function:sendText"
    assert kw["InvocationType"] == "RequestResponse"
    assert json.loads(kw["Payload"].decode("utf-8")) == {"subject": "Your reminder",
                                                         "message": "Commuter lunch, Tue Oct 13, 12:30, Robeson."}
    assert ("lambda", "us-east-1") in fake_aws.regions


def test_email_error_string(fake_aws):
    fake_aws("lambda", invoke=RuntimeError("denied"))
    assert assist_aws.send_email_notification("s", "m") == "Could not send email: denied"


def test_real_lambda_is_blocked_in_tests():
    # the autouse guard in tests/conftest.py: an unpatched call never reaches AWS
    assert assist_aws.send_email_notification("s", "m").startswith("Could not send email: tests must not invoke")


# ------------------------------------------------------------------------------------------------ tool wiring
def _tc():
    from app.auth import SessionCtx
    from app.chat.prompt import PromptBundle
    from app.chat.tools import ToolContext
    from app import clock
    return ToolContext(ctx=SessionCtx("t", "andre", "x1"), bundle=PromptBundle(system="", catalog_ids=set(), profile="",
                                                                                 memory=""),
                       now=clock.default_now(), emit=lambda ui: None)


def test_make_tools_adds_kb_and_email_with_voice_bot_specs(fake_aws):
    from app.chat.tools import STATUS, STATUS_ES, make_tools, status_text
    tools = {t.tool_name: t for t in make_tools(_tc())}
    assert {"search_events", "search_knowledge_base", "send_email_notification"} <= set(tools)
    kb_spec = tools["search_knowledge_base"].tool_spec
    assert kb_spec["description"].startswith("Search the Rutgers knowledge base for official university information")
    assert list(kb_spec["inputSchema"]["json"]["properties"]) == ["query"]
    assert list(tools["send_email_notification"].tool_spec["inputSchema"]["json"]["properties"]) == ["subject", "message"]
    for name in ("search_knowledge_base", "send_email_notification"):
        assert name in STATUS and name in STATUS_ES
    assert status_text("search_knowledge_base", "es") != status_text("search_knowledge_base", "en")

    fake_aws("bedrock-agent-runtime", retrieve={"retrievalResults": [{"content": {"text": "Open 24/7 during finals."}}]})
    lam = fake_aws("lambda", invoke={"StatusCode": 200})
    assert tools["search_knowledge_base"](query="library hours") == "Open 24/7 during finals."
    assert tools["send_email_notification"](subject="Hi", message="Details") == "Email sent successfully."
    assert len(lam.calls) == 1


# ------------------------------------------------------------------------------------------------ models
def test_chat_model_is_haiku_in_us_east_1_without_native_guardrail(monkeypatch):
    from app.chat.agent import make_model
    from config.settings import get_settings
    monkeypatch.setattr(get_settings(), "guardrail_id", "old-guardrail")      # the old one must not be attached
    m = make_model()
    assert m.client.meta.region_name == "us-east-1"
    cfg = m.get_config()
    assert cfg["model_id"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert not cfg.get("guardrail_id")
