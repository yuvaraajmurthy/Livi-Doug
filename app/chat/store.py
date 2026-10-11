"""Chat persistence: turns per conversation, so a stateless server can rebuild the agent's context."""
import secrets

from psycopg.types.json import Jsonb

HISTORY_TURNS = 12


def new_conversation_id() -> str:
    return "c-" + secrets.token_urlsafe(8)


def latest_conversation(c, student_id: str) -> str | None:
    r = c.execute("SELECT id FROM chat_conversations WHERE student_id = %s ORDER BY created_at DESC LIMIT 1", (student_id,)).fetchone()
    return r["id"] if r else None


def start(c, student_id: str, conversation_id: str | None = None) -> str:
    conv = conversation_id or new_conversation_id()
    c.execute("INSERT INTO chat_conversations (id, student_id) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING", (conv, student_id))
    return conv


def add(c, student_id: str, conversation_id: str, role: str, text: str, blocks: list | None = None,
        source: str | None = None, at=None) -> int:
    start(c, student_id, conversation_id)
    return c.execute(
        """INSERT INTO chat_messages (student_id, conversation_id, role, text, blocks, source, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, coalesce(%s, now())) RETURNING id""",
        (student_id, conversation_id, role, text, Jsonb(blocks or []), source, at)).fetchone()["id"]


def messages(c, student_id: str, conversation_id: str, limit: int = 40) -> list[dict]:
    rows = c.execute(
        """SELECT id, role, text, blocks, source, created_at FROM chat_messages
           WHERE student_id = %s AND conversation_id = %s ORDER BY id DESC LIMIT %s""",
        (student_id, conversation_id, limit)).fetchall()
    return list(reversed(rows))


def agent_history(rows: list[dict]) -> list[dict]:
    """Strands messages for the last turns: text only, with a note of what was shown, strictly alternating roles."""
    out: list[dict] = []
    for r in rows[-HISTORY_TURNS:]:
        text = r["text"] or ""
        shown = [i["title"] for b in (r["blocks"] or []) if b.get("type") == "events" for i in b.get("items", [])]
        if shown:
            text = (text + f"\n[Shown as buttons: {'; '.join(shown)}]").strip()
        if not text:
            continue
        if out and out[-1]["role"] == r["role"]:
            out[-1]["content"][0]["text"] += "\n" + text
        else:
            out.append({"role": r["role"], "content": [{"text": text}]})
    while out and out[0]["role"] != "user":
        out.pop(0)
    if out and out[-1]["role"] == "user":  # the new user message is passed separately
        out.pop()
    return out


def user_turns(c, student_id: str, conversation_id: str) -> int:
    return c.execute("SELECT count(*) AS n FROM chat_messages WHERE student_id = %s AND conversation_id = %s AND role = 'user'",
                     (student_id, conversation_id)).fetchone()["n"]
