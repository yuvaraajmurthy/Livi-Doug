"""Chat-written memory (spec §3.4): what the student tells Compass, kept small, sourced, visible and deletable.

Design borrowed and adapted:
- mem0: extract facts, but ADD + supersede instead of a slow reconcile step. A fact with the same key replaces the
  visible statement and the old wording is kept in `source_ref.history` (nothing silently lost).
- OpenClaw: a "flush" pass writes durable facts from recent turns before they fall out of the context window.
- Hermes: facts are later injected as a bounded, frozen snapshot at the start of each conversation (prompt.py).
Safety: crisis or concern language, and health, medication or diagnosis statements are never stored."""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime

from psycopg.types.json import Jsonb

from app.safety.lexicon import scan

log = logging.getLogger("compass.chat.memory")

CAP = 25
KINDS = {"likes", "dislikes", "interest", "goal", "time_works", "constraint"}
USED_FOR = {
    "likes": "Suggestions lean toward this",
    "interest": "Suggestions lean toward this",
    "dislikes": "Suggestions steer around this",
    "time_works": "Suggestions fit this time",
    "constraint": "Respected when suggesting",
    "goal": "Keeps suggestions pointed at this",
}
_HEALTH = re.compile(
    r"\b(medicat\w*|meds|prescri\w*|diagnos\w*|therap(y|ist)|psychiatr\w*|antidepress\w*|ssris?|sertraline|zoloft|"
    r"prozac|lexapro|adderall|xanax|ritalin|depress\w*|bipolar|ptsd|adhd|ocd|eating disorder|anorexi\w*|bulimi\w*|"
    r"suicid\w*|self[- ]?harm\w*|overdos\w*|pills?)\b", re.I)
_STOP = {"i", "im", "i'm", "my", "me", "the", "a", "an", "to", "of", "and", "or", "for", "on", "in", "at", "is", "are",
         "am", "be", "really", "like", "likes", "love", "loves", "enjoy", "enjoys", "usually", "usually", "most", "now"}


@dataclass(frozen=True)
class Refused:
    reason: str


def _key(kind: str, fact: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", fact.lower()) if w not in _STOP]
    return f"chat:{kind}:" + "-".join(words[:3]) if words else f"chat:{kind}:x"


def check(fact: str) -> Refused | None:
    if len(fact) < 3:
        return Refused("empty")
    if scan(fact).label != "none":
        return Refused("safety")
    if _HEALTH.search(fact):
        return Refused("health")
    return None


def remember(conn, student_id: str, kind: str, fact: str, chat_message_id: int | None = None,
             now: datetime | None = None) -> dict | Refused:
    """Store (or supersede) one fact. Returns {"id": "m:<n>", "statement", "kind"} or Refused."""
    fact = " ".join((fact or "").split())[:140].rstrip(".")
    kind = kind if kind in KINDS else "interest"
    bad = check(fact)
    if bad:
        return bad
    from app import clock
    now = now or clock.default_now()
    key = _key(kind, fact)
    label = f"You said in chat · {now:%b} {now.day}"
    row = conn.execute("SELECT id, statement, source_ref, updated_at FROM student_memory WHERE student_id = %s AND kind = %s AND key = %s",
                       (student_id, kind, key)).fetchone()
    if row:
        ref = dict(row["source_ref"] or {})
        if row["statement"] != fact:
            ref["history"] = [{"statement": row["statement"], "at": row["updated_at"].isoformat()}] + list(ref.get("history", []))[:4]
        ref["chat_message_id"] = chat_message_id
        conn.execute("UPDATE student_memory SET statement = %s, source_label = %s, source_ref = %s, updated_at = %s WHERE id = %s",
                     (fact, label, Jsonb(ref), now, row["id"]))
        mid = row["id"]
    else:
        mid = conn.execute(
            """INSERT INTO student_memory (student_id, kind, key, statement, source_type, source_label, source_ref, confidence,
                                           used_for, created_at, updated_at)
               VALUES (%s, %s, %s, %s, 'your_words', %s, %s, 0.8, %s, %s, %s) RETURNING id""",
            (student_id, kind, key, fact, label, Jsonb({"chat_message_id": chat_message_id}), USED_FOR[kind], now, now),
        ).fetchone()["id"]
    _enforce_cap(conn, student_id)
    return {"id": f"m:{mid}", "statement": fact, "kind": kind}


def _enforce_cap(conn, student_id: str) -> None:
    conn.execute(
        """DELETE FROM student_memory WHERE id IN (
             SELECT id FROM student_memory WHERE student_id = %s AND source_type = 'your_words'
             ORDER BY updated_at DESC, id DESC OFFSET %s)""", (student_id, CAP))


def forget(conn, student_id: str, memory_id: str) -> bool:
    if not memory_id.startswith("m:") or not memory_id[2:].isdigit():
        return False
    return conn.execute("DELETE FROM student_memory WHERE id = %s AND student_id = %s",
                        (int(memory_id[2:]), student_id)).rowcount > 0


def recall(conn, student_id: str, query: str, k: int = 5) -> list[str]:
    """Search the student's memory facts and past chat turns (Postgres full-text)."""
    facts = conn.execute(
        """SELECT statement FROM student_memory WHERE student_id = %s
             AND to_tsvector('english', statement) @@ websearch_to_tsquery('english', %s) LIMIT %s""",
        (student_id, query, k)).fetchall()
    turns = conn.execute(
        """SELECT role, text, created_at FROM chat_messages WHERE student_id = %s
             AND to_tsvector('english', text) @@ websearch_to_tsquery('english', %s)
           ORDER BY id DESC LIMIT %s""", (student_id, query, k)).fetchall()
    return [f"Fact: {f['statement']}" for f in facts] + [f"{t['role']} said: {t['text'][:200]}" for t in turns]


FLUSH_EVERY = 6
_FLUSH_SYSTEM = """You extract durable personal facts a campus-wellness assistant should remember about a student.
Return JSON only: {"facts": [{"kind": "likes|dislikes|interest|goal|time_works|constraint", "fact": "short third-person phrase"}]}
At most 3 facts. Only lasting preferences, interests, schedule facts, constraints or goals the student stated about
themselves. Never health, medication, diagnosis, mood or crisis content. Never facts about other people. If none, {"facts": []}."""


def flush(conn, student_id: str, conversation_id: str) -> int:
    """OpenClaw-style memory flush over the student's recent turns. No-op when models are off. Returns facts stored."""
    from app.llm.bedrock import ModelUnavailable, converse
    from config.settings import get_settings
    turns = conn.execute(
        "SELECT text FROM chat_messages WHERE student_id = %s AND conversation_id = %s AND role = 'user' ORDER BY id DESC LIMIT %s",
        (student_id, conversation_id, FLUSH_EVERY)).fetchall()
    if not turns or get_settings().force_templates:
        return 0
    text = "\n".join(f"- {t['text']}" for t in reversed(turns))
    try:
        out = converse(get_settings().model_fast, f"Student messages:\n{text}", system=_FLUSH_SYSTEM, max_tokens=250,
                       timeout=6.0, temperature=0.0, purpose="memory_flush")
        data = json.loads(out[out.find("{"): out.rfind("}") + 1])
    except (ModelUnavailable, ValueError) as exc:
        log.info("memory flush skipped", extra={"outcome": type(exc).__name__})
        return 0
    n = 0
    for f in (data.get("facts") or [])[:3]:
        if isinstance(f, dict) and not isinstance(remember(conn, student_id, str(f.get("kind", "")), str(f.get("fact", ""))), Refused):
            n += 1
    return n
