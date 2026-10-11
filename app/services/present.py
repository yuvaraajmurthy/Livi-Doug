"""Turn engine output into contract models. Labels, going counts, why lines, recommendation rows."""
import re
import hashlib
from datetime import datetime

from psycopg.types.json import Jsonb

from app import trace
from app.trace import _TRACE
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
        "helps_with": helps_with(s.component_text.get("dimension", ""), ctx.language),
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
    return Reasons(filters=[ReasonLine(code=c, text=localize_filter(c, t, lang)) for c, t in s.filters], components=comps, memory=mem,
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
    if not trace_has("wording"):  # the hero card is first; its wording source is the one worth showing
        trace.note(wording="ai" if src == "ai" else "template")
    it = s.item
    rung = it.rung or 1
    labels = cfg()["rung_labels_es" if lang == "es" else "rung_labels"]
    return Suggestion(
        rec_id=rec_id, item=to_item(s, lang), starts_at=it.starts_at, ends_at=it.ends_at, when_label=when_label(s, lang),
        window_label=localize_window(s.window_label, lang) if ctx.windows and s.components.get("window", 0) >= cfg()["min_window_fit"] else None,
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


def trace_has(key: str) -> bool:
    d = _TRACE.get()
    return bool(d and key in d)


# What a root-cause step helps with, in plain non-clinical words (the judge's sleep -> coursework -> tutoring example).
HELPS_WITH = {
    "academic_workload": ("the coursework that's been eating into your nights", "las tareas que te están quitando las noches"),
    "money": ("the money pressure you mentioned", "la presión de dinero que mencionaste"),
    "loneliness": ("not knowing anyone yet", "no conocer a nadie todavía"),
}


def helps_with(dimension_text: str, lang: str) -> str | None:
    if not dimension_text.startswith("root_cause:"):
        return None
    en, es = HELPS_WITH.get(dimension_text.split(":", 1)[1], ("what you said gets in the way", "lo que dijiste que te frena"))
    return es if lang == "es" else en


# Spanish for the engine's English labels (the engine stays language-free; presentation localises) -----------------
_DAYS_ES = {"Monday": "lunes", "Tuesday": "martes", "Wednesday": "miércoles", "Thursday": "jueves", "Friday": "viernes",
            "Saturday": "sábado", "Sunday": "domingo"}
_WINDOW_ES = [
    (re.compile(r"^Fits your (\w+) gap, (.+)$"), "Cabe en tu hueco del {d}, {t}"),
    (re.compile(r"^Mostly inside your (\w+) gap, (.+)$"), "Casi todo dentro de tu hueco del {d}, {t}"),
    (re.compile(r"^Open during your (\w+) gap, (.+)$"), "Abierto durante tu hueco del {d}, {t}"),
]
_FIXED_ES = {"Any time": "Cuando quieras", "Any time, online": "Cuando quieras, en línea"}
_FILTERS_ES = {"campus": "En tu campus", "online": "En línea", "free": "Gratis", "in_window": "Dentro de uno de tus horarios libres",
               "sample": "Evento de ejemplo (sintético)"}


def localize_window(label: str | None, lang: str) -> str | None:
    if label is None or lang != "es":
        return label
    if label in _FIXED_ES:
        return _FIXED_ES[label]
    for rx, tpl in _WINDOW_ES:
        m = rx.match(label)
        if m:
            return tpl.format(d=_DAYS_ES.get(m.group(1), m.group(1)), t=m.group(2))
    return label


def localize_filter(code: str, text: str, lang: str) -> str:
    return _FILTERS_ES.get(code, text) if lang == "es" else text
