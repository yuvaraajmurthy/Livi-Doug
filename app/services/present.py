"""Turn engine output into contract models. Labels, going counts, why lines, recommendation rows."""
import hashlib
from datetime import datetime

from psycopg.types.json import Jsonb

from app.engine.rank import DAY_NAMES, cfg
from app.engine.types import RankResult, Scored, StudentCtx
from app.llm import wording
from app.models.common import GoingCount, Item, Place, SourceRef
from app.models.student import Component, MemoryReason, ReasonLine, Reasons, Suggestion
from app.repo.kb import going_count

DAY_ES = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MON_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
CAMPUS_LABEL = {"newark": "Newark", "camden": "Camden", "new_brunswick": "New Brunswick", "online": "online"}


def clock_label(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d}" if dt.minute else f"{h}"


def ampm(dt: datetime) -> str:
    return "AM" if dt.hour < 12 else "PM"


def when_label(s: Scored, lang: str) -> str:
    it = s.item
    es = lang == "es"
    if it.kind == "micro":
        return "Hoy" if es else "Today"
    if it.starts_at is None:
        if it.campus == "online":
            return "Cuando quieras" if es else "Any time"
        return "Esta semana" if es else "This week"
    st, en = it.starts_at, it.ends_at
    day = f"{DAY_ES[st.weekday()]} {st.day} {MON_ES[st.month - 1]}" if es else f"{st:%a} {st:%b} {st.day}"
    if it.all_day:
        return f"{day}, todo el día" if es else f"{day}, all day"
    if en:
        same = ampm(st) == ampm(en)
        return f"{day}, {clock_label(st)}{'' if same else ' ' + ampm(st)}–{clock_label(en)} {ampm(en)}"
    return f"{day}, {clock_label(st)} {ampm(st)}"


def cost_label(cost: str, lang: str, kind: str) -> str:
    if lang == "es":
        return {"free": "Gratis", "paid": "Con costo", "unknown": "Costo no indicado"}[cost]
    if cost == "free":
        return "Free for students" if kind in ("resource", "place") else "Free"
    return {"paid": "Costs money", "unknown": "Cost not listed"}[cost]


def going(conn, s: Scored, campus: str, lang: str) -> GoingCount:
    if s.item.starts_at is None:
        return GoingCount(count=None, label="")
    n = going_count(conn, s.item.id)
    if n >= 5:
        where = CAMPUS_LABEL.get(campus, "")
        return GoingCount(count=n, label=(f"Van {n} estudiantes de {where}" if lang == "es" else f"{n} {where} students are going"))
    if n >= 1:
        return GoingCount(count=None, label="Van algunos estudiantes" if lang == "es" else "A few students are going")
    return GoingCount(count=None, label="")


def why_facts(s: Scored, ctx: StudentCtx) -> dict:
    it = s.item
    barriers_hit = [b for b in s.component_text.get("barrier", "").split(", ") if b]
    return {
        "title": it.title.replace(" (sample)", ""),
        "kind": it.kind,
        "focus_area": ctx.focus,
        "window_label": s.window_label if s.components.get("window", 0) >= 0.9 and ctx.windows else None,
        "walk_min": s.walk_min,
        "cost": it.cost,
        "barriers_hit": barriers_hit,
        "rung_label": cfg()["rung_labels"].get(it.rung or 1),
        "root_cause": s.component_text.get("dimension", "").startswith("root_cause"),
        "online": it.campus == "online",
        "venue": it.venue,
        "summary": (it.summary or "")[:200] or None,
    }


def reasons(s: Scored, lang: str) -> Reasons:
    w = cfg()["weights"]
    comp_text = dict(s.component_text)
    d = comp_text.get("dimension", "")
    if d.startswith("root_cause:"):
        comp_text["dimension"] = "Addresses what's cutting into your sleep (coursework)" if "academic" in d else "Addresses the root cause you named"
    comps = [Component(name=k, weight=w[k], score=round(s.components[k], 3), contribution=round(w[k] * s.components[k], 3),
                       text=comp_text.get(k, "")) for k in w]
    mem = [MemoryReason(memory_id=f"m:{f.id}", statement=f.statement, delta=dlt) for f, dlt in s.memory]
    return Reasons(filters=[ReasonLine(code=c, text=t) for c, t in s.filters], components=comps, memory=mem,
                   distance=s.distance_note, total=round(s.score, 3))


def to_item(s: Scored, lang: str) -> Item:
    it = s.item
    title = it.title
    summary = (it.summary_es if lang == "es" and it.summary_es else it.summary)
    if it.kind == "micro" and lang == "es" and it.summary_es:
        title, summary = it.summary_es, None
    return Item(id=it.id, kind=it.kind, title=title, summary=summary, dimensions=[d for d in it.dims if d in (
        "emotional", "environmental", "financial", "intellectual", "occupational", "physical", "social", "spiritual")],
        url=it.url, phone=it.phone, hours_text=it.hours_text, synthetic=it.synthetic)


def suggestion(conn, s: Scored, rec_id: int, ctx: StudentCtx, pushed: bool) -> Suggestion:
    lang = ctx.language
    why, src = wording.get(conn, "why", why_facts(s, ctx), lang)
    it = s.item
    rung = it.rung or 1
    labels = cfg()["rung_labels_es" if lang == "es" else "rung_labels"]
    return Suggestion(
        rec_id=rec_id, item=to_item(s, lang), starts_at=it.starts_at, ends_at=it.ends_at, when_label=when_label(s, lang),
        window_label=s.window_label if ctx.windows and s.components.get("window", 0) >= cfg()["min_window_fit"] else None,
        where=Place(venue=it.venue, address=it.address, lat=it.lat, lon=it.lon, campus=it.campus if it.campus in (
            "new_brunswick", "newark", "camden", "online", "community") else "online"),
        walk_min=s.walk_min, cost=it.cost, cost_label=cost_label(it.cost, lang, it.kind), rung=rung,
        rung_label=labels.get(rung), going=going(conn, s, ctx.campus, lang), reasons=reasons(s, lang), why=why,
        why_source="ai" if src == "ai" else "template", pushed=pushed,
        source=SourceRef(name=it.attribution or it.source or "Compass", url=it.source_url or it.url, verified_on=it.verified_on),
    )


def set_id_for(ctx: StudentCtx, result: RankResult, now: datetime) -> str:
    ids = ",".join(p.item.id for p in result.picks)
    raw = f"{ctx.id}|{ctx.focus}|{','.join(ctx.barriers)}|{ctx.target_rung}|{now.date()}|{ids}"
    return "set-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def persist_set(conn, ctx: StudentCtx, result: RankResult, now: datetime, pushed: bool, engine_version: str) -> tuple[str, list[int]]:
    """Insert the recommendation rows once per (student, inputs, picks, day); reuse ids when unchanged."""
    sid = set_id_for(ctx, result, now)
    rows = conn.execute("SELECT id, item_id FROM recommendations WHERE student_id = %s AND set_id = %s ORDER BY rank",
                        (ctx.id, sid)).fetchall()
    if rows and [r["item_id"] for r in rows] == [p.item.id for p in result.picks]:
        return sid, [r["id"] for r in rows]
    ids = []
    for rank_i, p in enumerate(result.picks):
        rr = conn.execute(
            """INSERT INTO recommendations (student_id, item_id, dimension, rung, shown_on, shown_at, status, set_id, rank, reasons,
                                            engine_version, pushed)
               VALUES (%s, %s, %s, %s, %s, %s, 'shown', %s, %s, %s, %s, %s) RETURNING id""",
            (ctx.id, p.item.id, ctx.focus or "emotional", p.item.rung, now.date(), now, sid, rank_i,
             Jsonb({"components": p.components, "filters": [c for c, _ in p.filters], "memory": [f.id for f, _ in p.memory],
                    "score": p.score}), engine_version, pushed),
        ).fetchone()
        ids.append(rr["id"])
    return sid, ids


DAY_NAMES = DAY_NAMES
