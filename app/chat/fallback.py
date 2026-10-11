"""Deterministic responder when models are off or slow: real events picked by search + catalog keyword overlap,
a template line, and the same `events` UI block. The chat never dead-ends."""
import re
from zoneinfo import ZoneInfo

from app.chat import catalog
from app.chat.prompt import PromptBundle
from app.repo import kb

TEXT = {
    "en": ("Here are a few things on your campus that could fit.", "I couldn't find a match for that. Try asking about a time, a place or a kind of event."),
    "es": ("Aquí tienes algunas opciones en tu campus que podrían servirte.", "No encontré algo así. Prueba con un horario, un lugar o un tipo de evento."),
}


def _overlap(query: str, bundle: PromptBundle) -> list[str]:
    words = {w for w in re.findall(r"[a-z]{3,}", query.lower())}
    scored = []
    for iid, it in bundle.items.items():
        hay = f"{it.title} {it.summary or ''} {it.venue or ''} {' '.join(it.dims)}".lower()
        s = sum(1 for w in words if w in hay)
        if s:
            scored.append((-s, it.starts_at is None, iid))
    return [i for *_, i in sorted(scored)]


def respond(c, query: str, bundle: PromptBundle, now) -> tuple[str, list[dict]]:
    """Return (text, chips)."""
    ids: list[str] = []
    try:
        from app.ask.retrieval import search
        rows, _ = search(c, query, bundle.campus, now.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None), k=3)
        ids = [r["id"] for r in rows]
    except Exception:  # retrieval is best-effort here
        ids = []
    for i in _overlap(query, bundle):
        if len(ids) >= 3:
            break
        if i not in ids:
            ids.append(i)
    lang = "es" if bundle.language == "es" else "en"
    if not ids:
        return TEXT[lang][1], []
    items = {i.id: i for i in kb.load_items(c, bundle.campus, now, ids=ids[:3])}
    chips = [catalog.chip(items[i], lang) for i in ids[:3] if i in items]
    return (TEXT[lang][0] if chips else TEXT[lang][1]), chips
