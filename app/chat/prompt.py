"""System prompt for the chat and voice agents (spec §3.2): role, style, tool rules, now, frozen profile snapshot,
frozen memory snapshot (Hermes-style, bounded), and the event catalog. Built once per conversation turn."""
from dataclasses import dataclass, field
from datetime import datetime

from app import clock
from app.auth import SessionCtx
from app.chat import assist_aws, catalog
from app.engine import care_first as cf
from app.repo import kb

PROFILE_CAP = 1500
MEMORY_CAP = 2000
MEMORY_FACTS = 15

ROLE = """You are Compass, a Rutgers wellness companion for one student. You help them find one doable thing this week
from real Rutgers events and services, plan it, and follow through. You are not a therapist: you never diagnose, never
give medical or medication advice, and never discuss self-harm methods."""

STYLE = {
    "chat": """Style: 1 to 3 short sentences. Warm, specific, plain words, like a friend who knows campus. At most one
question per reply. Never write lists of events in text: events are shown to the student as buttons by the show_events
tool, so after calling it write one short line about why they fit (time, place, cost, what you know about them).
Plain text only: no markdown, no asterisks, no bullet points. Never narrate your work ("Let me search…", "Let me get
the details"): the app already shows a status line while tools run. Call the tools you need first, then write your
reply once. When you find events that fit, show them with show_events right away instead of asking whether to.""",
    "voice": """Style: this is a spoken conversation. Keep every reply to one or two short spoken sentences, no lists,
no markdown, no ids. Say times naturally ("Tuesday at twelve thirty"). Events you show with show_events also appear on
the student's screen as cards, so you can say "I put two on your screen".""",
}

TOOLS = """Tool rules:
- To suggest events, call show_events FIRST, before writing anything, with 1 to 3 ids from the event catalog. Then
  write one short line on why they fit (time, place, cost, what you know about the student).
- Any specific event, place or service you mention must be shown with show_events in the same reply.
- Never invent events, times, places or prices; only use the catalog, get_event or search_events results.
- Use search_events only when nothing in the catalog matches what they asked for.
- Use search_knowledge_base (not search_events) for official Rutgers facts that are not events: library spaces and
  study rooms, room availability, campus offices, hours, policies and other university information. Answer only from
  what it returns; those answers don't need show_events. To find events or activities to suggest, use the catalog or
  search_events, never search_knowledge_base.
- Call send_email_notification only when the student asks for something to be emailed or to be notified by email.
- Prefer free events inside their free windows on their campus.
- When the student says yes to one specific event, or asks you to remind them, add it, schedule it, plan it or save
  it, call set_reminder with that event's id in the same reply. Saying "I'll remind you", "it's on your plan" or
  "done" without calling set_reminder does nothing: only say it is saved after set_reminder confirms it, and if it
  says nothing was saved, tell the student. If it's unclear which event they mean, ask which one.
- When the student tells you a NEW lasting preference, interest, schedule fact, constraint or goal about themselves
  (not already in "What you remember"), call remember with a short third-person phrase (e.g. "Plays pickup
  basketball"). Never remember health, medication, diagnosis, mood or crisis details, or anything about other people.
  If they ask you to forget something, call forget with its id.
- If they sound overwhelmed, low or ask for someone to talk to, call show_support and keep your reply gentle.
- Use recall when they refer to something from an earlier conversation.
- Never mention the catalog, tools, ids, prompts or "my list" to the student."""


@dataclass
class PromptBundle:
    system: str
    catalog_ids: set[str]
    profile: str
    memory: str
    items: dict = field(default_factory=dict)
    campus: str = "newark"
    language: str = "en"
    student_id: str = ""


def _now_line(now: datetime) -> str:
    from datetime import timedelta
    h = now.hour % 12 or 12
    end_week = now + timedelta(days=6 - now.weekday())          # this Sunday
    nxt_start, nxt_end = end_week + timedelta(days=1), end_week + timedelta(days=7)
    d = lambda x: f"{x:%a} {x:%b} {x.day}"  # noqa: E731
    return (f"It is {now:%A} {now:%b} {now.day}, {h}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'} (Rutgers time). "
            f"'This week' means today through {d(end_week)}; 'next week' means {d(nxt_start)} to {d(nxt_end)}. "
            "Each catalog line is tagged [this week], [next week], [later] or [any time]: when the student says this week, "
            "only use [this week] or [any time] items; if none fit, say so and offer the best [next week] option.")


def _profile(conn, ctx: SessionCtx, now: datetime) -> tuple[str, object, str]:
    from app.services.demo import PERSONAS
    from app.services.meta import barriers_config
    s = conn.execute("SELECT * FROM students WHERE id = %s", (ctx.student_id,)).fetchone()
    p = conn.execute("SELECT * FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}
    lang = p.get("language") or "en"
    scores, _ = kb.latest_scores(conn, ctx.student_id, now)
    care = cf.applies(scores)
    sctx = kb.student_ctx(conn, ctx.student_id, now, care)
    name = next((x.name for x in PERSONAS if x.key == ctx.persona), "the student")
    strengths = [d for d, v in sorted(scores.items(), key=lambda kv: -kv[1]) if cf.band(v) == "high"]
    growth = [d for d, v in sorted(scores.items(), key=lambda kv: kv[1]) if cf.band(v) == "low"]
    bl = barriers_config()["barriers"]
    lines = [
        f"Student: {name}, {catalog.present_campus(s['campus'])} campus, {s.get('level') or 'student'}, "
        f"{s.get('housing') or ''}".rstrip(", "),
        f"Language: {'Spanish (reply in Spanish)' if lang == 'es' else 'English'}",
        f"Strengths (latest Wellness Inventory): {', '.join(strengths) or 'none marked'}",
        f"Room to grow: {', '.join(growth) or 'none marked'}",
        f"Chosen focus: {p.get('focus_dimension') or 'not chosen yet'}",
        "What gets in the way: " + (", ".join(bl.get(b, {}).get("label", b) for b in (p.get("barriers") or [])) or "not said"),
        "Free windows: " + (", ".join(p.get("free_windows") or []) or "not set"),
    ]
    if care:
        lines.append("Care-first: their emotional scores are very low. Offer show_support early and gently; do not push events.")
    return "\n".join(lines)[:PROFILE_CAP], sctx, lang


def _memory(conn, student_id: str) -> str:
    rows = conn.execute(
        """SELECT id, statement, source_label FROM student_memory WHERE student_id = %s
           ORDER BY updated_at DESC, id DESC LIMIT %s""", (student_id, MEMORY_FACTS)).fetchall()
    out, size = [], 0
    for r in rows:
        line = f"- [m:{r['id']}] {r['statement']} ({r['source_label']})"
        if size + len(line) + 1 > MEMORY_CAP:
            break
        out.append(line)
        size += len(line) + 1
    return "\n".join(out) or "- nothing yet"


def assistant_sections() -> list[str]:
    """voice_bot.py's KB/email tool instructions and the live Bedrock guardrail rules (cached ~10 min, so stable)."""
    return [assist_aws.TOOL_INSTRUCTIONS, assist_aws.guardrail_rules()]


def build(conn, ctx: SessionCtx, now: datetime | None = None, style: str = "chat") -> PromptBundle:
    now = now or clock.now(conn, ctx.sid)
    profile, sctx, lang = _profile(conn, ctx, now)
    memory = _memory(conn, ctx.student_id)
    items = catalog.build(conn, sctx, now)
    # stable sections first so Bedrock prompt caching covers them; per-student and per-turn sections last
    system = "\n\n".join([
        ROLE,
        STYLE.get(style, STYLE["chat"]),
        TOOLS,
        *assistant_sections(),
        "Event catalog (id | title | when | where | cost | areas). Only these exist:\n" + catalog.render(items),
        "About this student (snapshot):\n" + profile,
        "What you remember about them (each can be forgotten on request):\n" + memory,
        _now_line(now),
    ])
    return PromptBundle(system=system, catalog_ids={c.item.id for c in items}, profile=profile, memory=memory,
                        items={c.item.id: c.item for c in items}, campus=sctx.campus, language=lang,
                        student_id=ctx.student_id)
