"""Event detail for the card (spec §3.7) and "Remind me" on any item: shared by the chat tools and the web card."""
from urllib.parse import quote_plus

from fastapi import HTTPException

from app import clock
from app.auth import SessionCtx
from app.db import conn
from app.engine import care_first as cf
from app.engine.rank import walk_minutes
from app.models.items import ItemDetail
from app.models.common import GoingCount, SourceRef
from app.models.loop import CommitRequest
from app.repo import kb
from app.services import present
from app.services.loop import _commit_response, _when, commit


def _directions(it) -> str:
    if it.lat is not None and it.lon is not None:
        return f"https://www.google.com/maps/dir/?api=1&destination={it.lat},{it.lon}"
    q = ", ".join(x for x in (it.venue, it.address) if x) or it.title
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(q)}"


def _calendar(it) -> str | None:
    if not it.starts_at:
        return None
    end = it.ends_at or it.starts_at
    fmt = "%Y%m%dT%H%M%SZ"
    from datetime import timezone
    dates = f"{it.starts_at.astimezone(timezone.utc):{fmt}}/{end.astimezone(timezone.utc):{fmt}}"
    loc = ", ".join(x for x in (it.venue, it.address) if x)
    return ("https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={quote_plus(it.title)}&dates={dates}&location={quote_plus(loc)}")


def load(c, ctx: SessionCtx, item_id: str):
    now = clock.now(c, ctx.sid)
    s = c.execute("SELECT campus FROM students WHERE id = %s", (ctx.student_id,)).fetchone()
    found = kb.load_items(c, s["campus"], now, ids=[item_id])
    if not found:
        raise HTTPException(404, detail={"error": "not_found", "message": "No such event or resource."})
    return found[0], now


def detail(ctx: SessionCtx, item_id: str) -> ItemDetail:
    with conn() as c:
        it, now = load(c, ctx, item_id)
        p = c.execute("SELECT language FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}
        lang = p.get("language") or "en"
        scores, _ = kb.latest_scores(c, ctx.student_id, now)
        sctx = kb.student_ctx(c, ctx.student_id, now, cf.applies(scores))
        n = kb.going_count(c, it.id) if it.starts_at else None
        going = GoingCount(count=n, label=(f"{n} students are going" if lang != "es" else f"{n} estudiantes van") if n else "")
        summary = it.summary_es if lang == "es" and it.summary_es else it.summary
        campus = it.campus if it.campus in ("new_brunswick", "newark", "camden", "online", "community") else "online"
        return ItemDetail(
            id=it.id, kind=it.kind, title=it.title, summary=summary, dimensions=list(it.dims), synthetic=it.synthetic,
            starts_at=it.starts_at, ends_at=it.ends_at, when_label=_when(it, lang), venue=it.venue, address=it.address,
            lat=it.lat, lon=it.lon, campus=campus, cost=it.cost, cost_label=present.cost_label(it.cost, lang, it.kind),
            url=it.url, phone=it.phone, hours_text=it.hours_text, walk_min=walk_minutes(sctx, it), going=going,
            source=SourceRef(name=it.attribution or it.source or "Compass", url=it.source_url or it.url, verified_on=it.verified_on),
            directions_url=_directions(it), calendar_url=_calendar(it), ics_url=None,
        )


def remind(ctx: SessionCtx, item_id: str, via: str = "card"):
    """Plan + reminder for one item. Reuses an open plan for the same item (idempotent)."""
    with conn() as c:
        it, now = load(c, ctx, item_id)
        existing = c.execute(
            "SELECT * FROM commitments WHERE student_id = %s AND item_id = %s AND status = 'planned' ORDER BY id DESC LIMIT 1",
            (ctx.student_id, item_id)).fetchone()
        if existing:
            p = c.execute("SELECT language FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}
            return _commit_response(c, existing, it, now, p.get("language") or "en")
        if it.starts_at and it.starts_at <= now:  # same rule as commit(), checked before leaving a stray suggestion row
            raise HTTPException(409, detail={"error": "already_started", "message": "That one has already started. Try another step."})
        focus =(c.execute("SELECT focus_dimension FROM profiles WHERE student_id = %s", (ctx.student_id,)).fetchone() or {}).get("focus_dimension")
        dim = focus or (max(it.dims, key=it.dims.get) if it.dims else "social")
        rec_id = c.execute(
            """INSERT INTO recommendations (student_id, item_id, dimension, rung, shown_on, shown_at, status, set_id, rank, reasons,
                                            engine_version, pushed)
               VALUES (%s, %s, %s, %s, %s, %s, 'shown', %s, 0, '{}'::jsonb, %s, false) RETURNING id""",
            (ctx.student_id, it.id, dim, it.rung, now.date(), now, f"{via}-{now:%Y%m%d}", via)).fetchone()["id"]
    return commit(ctx, CommitRequest(rec_id=rec_id))
