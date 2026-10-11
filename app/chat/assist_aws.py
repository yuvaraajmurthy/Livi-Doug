"""The team's tested voice_bot.py assistant pieces, ported faithfully: the Bedrock guardrail turned into prompt rules,
the Rutgers knowledge base (Bedrock KB retrieve) and the email notification Lambda. Same ids, strings and behaviour;
the only additions are the default boto3 credential chain (no profile), short timeouts, and caching of the guardrail
text so it is not fetched on every turn. Everything runs in settings.assistant_region (us-east-1)."""
import json
import logging
import threading
import time
from functools import lru_cache

import boto3
from botocore.config import Config

from config.settings import get_settings

log = logging.getLogger("compass.assist")

GUARDRAIL_TTL_S = 600.0        # a fetched guardrail is reused for 10 minutes
GUARDRAIL_FAIL_TTL_S = 60.0    # after a failed fetch, retry at most once a minute

# voice_bot.py tool instructions (used in the system prompt of both chat and voice)
TOOL_INSTRUCTIONS = (
    "Use the search_knowledge_base tool to look up library spaces, room availability, and campus information.\n"
    "When the user asks to send information, summaries, or links to their email "
    "(for example 'can you send that to my email?'), invoke the send_email_notification tool "
    "with an appropriate subject and message summarizing the information.\n"
    "Also invoke send_email_notification when the user asks to be notified by email (for example about a reminder "
    "they just set), with a subject and a message summarizing the details. Never ask for their email address."
)

# voice_bot.py fallback when the guardrail cannot be fetched (verbatim)
FALLBACK = (
    "You are the Rutgers student assistant voice agent. "
    "Use search_knowledge_base for university questions. "
    "Use send_email_notification when the user requests an email. "
    "Keep responses concise and conversational."
)
DEFAULT_BLOCKED = "I cannot fulfill this request. Please contact campus student services directly."

_TIMEOUTS = {
    "bedrock": Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 2, "mode": "standard"}),
    "bedrock-agent-runtime": Config(connect_timeout=3, read_timeout=20, retries={"max_attempts": 2, "mode": "standard"}),
    # one attempt only: a retried invoke could send the same email twice
    "lambda": Config(connect_timeout=3, read_timeout=30, retries={"max_attempts": 1, "mode": "standard"}),
}


@lru_cache(maxsize=8)
def client(service: str, region: str):
    """boto3 client on the default credential chain (no named profile)."""
    return boto3.session.Session(region_name=region).client(service, config=_TIMEOUTS.get(service))


def _client(service: str):
    return client(service, get_settings().assistant_region)


# ------------------------------------------------------------------------------------------------ knowledge base
def search_knowledge_base(query: str) -> str:
    s = get_settings()
    try:
        response = _client("bedrock-agent-runtime").retrieve(
            knowledgeBaseId=s.bedrock_knowledge_base_id,
            retrievalQuery={"text": query},
        )
        results = response.get("retrievalResults", [])
        if not results:
            return "No matching information found in knowledge base."
        return "\n\n".join(
            r.get("content", {}).get("text", "") for r in results
        )
    except Exception as error:
        return f"Could not retrieve from knowledge base: {error}"


# ------------------------------------------------------------------------------------------------ email
def send_email_notification(subject: str, message: str) -> str:
    s = get_settings()
    try:
        payload = json.dumps({"subject": subject, "message": message})
        _client("lambda").invoke(
            FunctionName=s.send_text_lambda_arn,
            InvocationType="RequestResponse",
            Payload=payload.encode("utf-8"),
        )
        return "Email sent successfully."
    except Exception as error:
        return f"Could not send email: {error}"


# ------------------------------------------------------------------------------------------------ guardrail
def load_guardrail_from_bedrock(guardrail_id: str, version: str) -> str:
    """The guardrail's live config as prompt rules ("ACTIVE BEDROCK GUARDRAIL RULES"), or FALLBACK if the fetch fails."""
    try:
        response = _client("bedrock").get_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=version,
        )
    except Exception as error:
        log.warning("could not fetch guardrail from bedrock: %s", error)
        return FALLBACK

    blocked_msg = response.get("blockedInputMessaging", DEFAULT_BLOCKED)

    topics = response.get("topicPolicy", {}).get("topics", [])
    topic_lines = []
    for idx, topic in enumerate(topics, 1):
        name = topic.get("name", "")
        definition = topic.get("definition", "")
        topic_lines.append(f"{idx}. {name}: {definition}")
    topic_text = "\n".join(topic_lines)

    return (
        "ACTIVE BEDROCK GUARDRAIL RULES:\n"
        "You must follow the active Amazon Bedrock Guardrail policies below.\n"
        "Never provide answers for the following restricted topics:\n"
        f"{topic_text}\n\n"
        f'If any restricted topic or sensitive PII is mentioned, decline immediately with: "{blocked_msg}"\n'
    )


_cache: dict[tuple, tuple[float, str]] = {}
_lock = threading.Lock()


def guardrail_rules() -> str:
    """Cached load_guardrail_from_bedrock for the configured guardrail. No AWS call when Bedrock is switched off."""
    s = get_settings()
    if not s.bedrock_enabled:
        return FALLBACK
    key = (s.bedrock_guardrail_id, s.bedrock_guardrail_version, s.assistant_region)
    hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        text = load_guardrail_from_bedrock(s.bedrock_guardrail_id, s.bedrock_guardrail_version)
        ttl = GUARDRAIL_FAIL_TTL_S if text == FALLBACK else GUARDRAIL_TTL_S
        _cache[key] = (time.monotonic() + ttl, text)
        return text


def clear_cache() -> None:
    _cache.clear()
    getattr(client, "cache_clear", lambda: None)()
