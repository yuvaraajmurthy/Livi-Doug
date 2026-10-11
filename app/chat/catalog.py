"""The event catalog the chat agent sees in its system prompt: one compact line per real item, nothing invented.

`id | title | when | where | cost | dimensions` for the student's campus plus online, next 14 days, plus always-open
resources. The agent may only show events by these ids (tools validate)."""
from dataclasses import dataclass
from datetime import datetime

from app.engine.types import KbItem, StudentCtx
from app.repo import kb
from app.services import present

MAX_ROWS = 80
HORIZON_DAYS = 14


@dataclass(frozen=True)
class CatalogItem:
    item: KbItem
    when: str
    where: str
    cost: str
    dims: str
    rel: str = ""


def relative(it: KbItem, now: datetime) -> str:
    """[this week] / [next week] / [later] / [any time]: explicit tags the model follows better than date math."""
    from datetime import timedelta
    if not it.starts_at:
        return "any time"
    end_week = (now + timedelta(days=6 - now.weekday())).date()
    d = it.starts_at.date()
    if d <= end_week:
        return "this week"
    if d <= end_week + timedelta(days=7):
        return "next week"
    return "later"


def _when(it: KbItem) -> str:
    from app.services.loop import _when as when
    return when(it, "en")


def build(conn, sctx: StudentCtx, now: datetime) -> list[CatalogItem]:
    items = [i for i in kb.load_items(conn, sctx.campus, now, HORIZON_DAYS) if i.kind != "micro"
             and (not i.audiences or sctx.campus in i.audiences)]
    # timed events first (soonest first), then always-open resources and places
    items.sort(key=lambda i: (i.starts_at is None, i.starts_at or now, i.title))
    out = []
    for it in items[:MAX_ROWS]:
        where = it.venue or ("Online" if it.campus == "online" else present_campus(it.campus))
        dims = ", ".join(sorted(it.dims, key=lambda d: -it.dims[d])[:2])
        out.append(CatalogItem(item=it, when=_when(it), where=where, cost=it.cost, dims=dims, rel=relative(it, now)))
    return out


def present_campus(campus: str) -> str:
    return {"new_brunswick": "New Brunswick", "newark": "Newark", "camden": "Camden"}.get(campus, campus)


def render(items: list[CatalogItem]) -> str:
    return "\n".join(f"{c.item.id} | {c.item.title} | [{c.rel}] {c.when} | {c.where} | {c.cost} | {c.dims}" for c in items)


def chip(it: KbItem, lang: str = "en") -> dict:
    """The button payload for one event (spec §3.6 EventChip)."""
    from app.services.loop import _when as when
    return {"id": it.id, "title": it.title, "when_label": when(it, lang), "venue": it.venue,
            "cost_label": present.cost_label(it.cost, lang, it.kind), "synthetic": it.synthetic, "kind": it.kind}
