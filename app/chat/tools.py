"""Tools for the chat/voice agent (spec §3.3). Bound per request to one student; every UI side effect goes through
`emit(UIEvent)` so the same tools drive chat (SSE) and voice (WebSocket). Tools validate everything: the model can
only show events that exist, and memory writes pass the safety rules in memory.py."""
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from strands import tool

from app.auth import SessionCtx
from app.chat import catalog, memory
from app.chat.prompt import PromptBundle
from app.db import conn
from app.repo import kb

NY_TZ = "America/New_York"


@dataclass
class ToolContext:
    ctx: SessionCtx
    bundle: PromptBundle
    now: datetime
    emit: Callable[[dict], None]
    user_message_id: int | None = None
    found: set[str] = field(default_factory=set)  # ids surfaced by search_events (also allowed in show_events)


STATUS = {
    "show_events": "Picking a few for you…",
    "get_event": "Looking at the details…",
    "search_events": "Searching Rutgers events…",
    "set_reminder": "Setting your reminder…",
    "remember": "Saving that…",
    "forget": "Forgetting that…",
    "recall": "Checking what I remember…",
    "show_support": "Finding someone to talk to…",
}
STATUS_ES = {
    "show_events": "Eligiendo algunas opciones…",
    "get_event": "Revisando los detalles…",
    "search_events": "Buscando eventos de Rutgers…",
    "set_reminder": "Creando tu recordatorio…",
    "remember": "Guardando eso…",
    "forget": "Olvidando eso…",
    "recall": "Revisando lo que recuerdo…",
    "show_support": "Buscando con quién hablar…",
}


def status_text(name: str, lang: str) -> str:
    return (STATUS_ES if lang == "es" else STATUS).get(name, "Working on it…")


def make_tools(tc: ToolContext) -> list:
    lang = tc.bundle.language

    @tool
    def show_events(event_ids: list[str], why: str = "") -> str:
        """Show 1 to 3 events or resources to the student as tappable buttons. Always use this to suggest events.

        Args:
            event_ids: Ids from the event catalog (or from search_events), best first. At most 3.
            why: One short phrase on why these fit this student.
        """
        allowed = tc.bundle.catalog_ids | tc.found
        ids = [i for i in dict.fromkeys(event_ids or []) if i in allowed][:3]
        if not ids:
            return "None of those ids exist. Use ids from the catalog, or call search_events."
        with conn() as c:
            items = {i.id: i for i in kb.load_items(c, tc.bundle.campus, tc.now, ids=ids)}
        chips = [catalog.chip(items[i], lang) for i in ids if i in items]
        tc.emit({"type": "events", "items": chips})
        return "Shown to the student as buttons: " + "; ".join(f"{c['title']} ({c['when_label']})" for c in chips)

    @tool
    def get_event(event_id: str) -> str:
        """Get full details of one event or resource (description, place, address, time, cost, link, phone).

        Args:
            event_id: An id from the catalog or from search_events.
        """
        with conn() as c:
            found = kb.load_items(c, tc.bundle.campus, tc.now, ids=[event_id])
        if not found:
            return "No such event."
        it = found[0]
        return json.dumps({"id": it.id, "title": it.title, "summary": it.summary, "when": catalog.chip(it)["when_label"],
                           "venue": it.venue, "address": it.address, "cost": it.cost, "url": it.url, "phone": it.phone,
                           "hours": it.hours_text, "sample_event": it.synthetic}, default=str)

    @tool
    def search_events(query: str) -> str:
        """Search all upcoming Rutgers events and services on the student's campus and online, beyond the catalog.

        Args:
            query: What to look for, in plain words (e.g. "free food", "math tutoring", "yoga").
        """
        from zoneinfo import ZoneInfo

        from app.ask.retrieval import search
        with conn() as c:
            rows, _ = search(c, query, tc.bundle.campus, tc.now.astimezone(ZoneInfo(NY_TZ)).replace(tzinfo=None), k=5)
        if not rows:
            return "Nothing found."
        tc.found.update(r["id"] for r in rows)
        return "\n".join(f"{r['id']} | {r['title']} | {r.get('venue') or ''}" for r in rows)

    @tool
    def set_reminder(event_id: str) -> str:
        """Make a plan and set a reminder for one event. Only call when the student clearly says yes to it.

        Args:
            event_id: The event the student chose.
        """
        from app.services.items import remind
        if event_id not in (tc.bundle.catalog_ids | tc.found):
            return "Unknown event id."
        r = remind(tc.ctx, event_id, via="chat")
        payload = r.model_dump(mode="json")
        if payload.get("kind") == "crisis":
            return "Could not set a reminder."
        tc.emit({"type": "plan", "plan": payload})
        return f"Reminder set. Plan: {payload.get('plan_text')} Reminder at {payload.get('reminder_at')}."

    @tool
    def remember(fact: str, kind: str = "interest") -> str:
        """Remember a lasting fact the student told you about themselves, as a short third-person phrase.

        Args:
            fact: e.g. "Plays pickup basketball", "Free on Fridays after 3", "Wants to make one friend this term".
            kind: One of likes, dislikes, interest, goal, time_works, constraint.
        """
        with conn() as c:
            r = memory.remember(c, tc.ctx.student_id, kind, fact, tc.user_message_id, tc.now)
        if isinstance(r, memory.Refused):
            return "Not saved (Compass doesn't keep that kind of detail). Do not mention saving it."
        tc.emit({"type": "memory", **r})
        return f"Saved as {r['id']}."

    @tool
    def forget(memory_id: str) -> str:
        """Forget one thing you remembered, when the student asks.

        Args:
            memory_id: The id shown in your memory list, like m:12.
        """
        with conn() as c:
            ok = memory.forget(c, tc.ctx.student_id, memory_id)
        if ok:
            tc.emit({"type": "memory_removed", "id": memory_id})
        return "Forgotten." if ok else "No such memory."

    @tool
    def recall(query: str) -> str:
        """Search what the student told you before (remembered facts and earlier chats).

        Args:
            query: Words to look for.
        """
        with conn() as c:
            hits = memory.recall(c, tc.ctx.student_id, query)
        return "\n".join(hits) or "Nothing found."

    @tool
    def show_support() -> str:
        """Show the student real people they can talk to on their campus (counseling, teletherapy, peer support)."""
        from app.safety import crisis
        card = crisis.support_card(tc.bundle.campus, lang)
        tc.emit({"type": "support", "card": card.model_dump(mode="json")})
        return "Support options shown: " + ", ".join(o.name for o in card.options)

    return [show_events, get_event, search_events, set_reminder, remember, forget, recall, show_support]
