"""Load engine inputs from Postgres."""
from datetime import datetime, timedelta

from app.clock import NY
from app.engine.rank import parse_window
from app.engine.types import HelpedStats, KbItem, MemoryFact, StudentCtx


def _aware(ts) -> datetime | None:
    if ts is None:
        return None
    return ts.replace(tzinfo=NY) if ts.tzinfo is None else ts.astimezone(NY)


def load_items(conn, campus: str, now: datetime, horizon_days: int = 10, ids: list[str] | None = None) -> list[KbItem]:
    """Candidate items for a campus (plus online and micro), or specific ids."""
    if ids is not None:
        rows = conn.execute("SELECT * FROM kb_items WHERE id = ANY(%s)", (ids,)).fetchall()
    else:
        local_now = now.astimezone(NY).replace(tzinfo=None)
        rows = conn.execute(
            """SELECT * FROM kb_items
               WHERE active AND campus IN (%s, 'online')
                 AND (starts_at IS NULL OR (coalesce(ends_at, starts_at + interval '1 hour') > %s AND starts_at <= %s))""",
            (campus, local_now, local_now + timedelta(days=horizon_days)),
        ).fetchall()
    if not rows:
        return []
    tags = conn.execute("SELECT item_id, tag_type, tag, confidence FROM kb_tags WHERE item_id = ANY(%s)",
                        ([r["id"] for r in rows],)).fetchall()
    by: dict[str, dict] = {}
    for t in tags:
        d = by.setdefault(t["item_id"], {"dimension": {}, "cause": set(), "barrier": set(), "format": set(), "audience": set()})
        if t["tag_type"] == "dimension":
            d["dimension"][t["tag"]] = max(float(t["confidence"]), d["dimension"].get(t["tag"], 0))
        elif t["tag_type"] in d:
            d[t["tag_type"]].add(t["tag"])
    out = []
    for r in rows:
        tg = by.get(r["id"], {"dimension": {}, "cause": set(), "barrier": set(), "format": set(), "audience": set()})
        out.append(KbItem(
            id=r["id"], kind=r["kind"], title=r["title"], campus=r["campus"], cost=r["cost"], summary=r["summary"],
            summary_es=r["summary_es"], venue=r["venue"], address=r["address"], lat=r["lat"], lon=r["lon"],
            starts_at=_aware(r["starts_at"]), ends_at=_aware(r["ends_at"]), rung=r["social_level"],
            solo_friendly=r["solo_friendly"], url=r["url"], phone=r["phone"], hours_text=r["hours_text"],
            open_hours=r["open_hours"], synthetic=r["synthetic"], demo_pin=r["demo_pin"], series_key=r["series_key"],
            formats=frozenset((r["formats"] or [])) | frozenset(tg["format"]), dims=tg["dimension"],
            causes=frozenset(tg["cause"]), barriers=frozenset(tg["barrier"]), audiences=frozenset(tg["audience"]), source=r["source"],
            attribution=r["attribution"], source_url=r["source_url"] or r["url"], verified_on=r["verified_on"],
            all_day=r["all_day"], arc_activity_id=r["arc_activity_id"],
        ))
    return out


def latest_scores(conn, student_id: str, now: datetime) -> tuple[dict[str, float], list[dict]]:
    """Scores of the latest take on or before simulated now, plus all visible takes (oldest first)."""
    takes = conn.execute(
        """SELECT t.id, t.take_no, t.taken_on, t.total FROM inventory_takes t
           WHERE t.student_id = %s AND t.taken_on <= %s ORDER BY t.taken_on""",
        (student_id, now.astimezone(NY).date()),
    ).fetchall()
    if not takes:
        return {}, []
    ids = [t["id"] for t in takes]
    rows = conn.execute("SELECT take_id, dimension, score FROM dimension_scores WHERE take_id = ANY(%s)", (ids,)).fetchall()
    per: dict[int, dict[str, float]] = {}
    for r in rows:
        per.setdefault(r["take_id"], {})[r["dimension"]] = float(r["score"])
    out = [{**t, "total": float(t["total"]), "scores": per.get(t["id"], {})} for t in takes]
    return out[-1]["scores"], out


def student_ctx(conn, student_id: str, now: datetime, care_first: bool) -> StudentCtx:
    s = conn.execute("SELECT * FROM students WHERE id = %s", (student_id,)).fetchone()
    p = conn.execute("SELECT * FROM profiles WHERE student_id = %s", (student_id,)).fetchone() or {}
    declined = conn.execute(
        "SELECT DISTINCT item_id FROM recommendations WHERE student_id = %s AND status = 'dismissed'", (student_id,)).fetchall()
    committed = conn.execute(
        "SELECT DISTINCT item_id FROM commitments WHERE student_id = %s AND status IN ('planned','went','missed')", (student_id,)).fetchall()
    windows = tuple(w for w in (parse_window(x) for x in (p.get("free_windows") or [])) if w)
    barriers = tuple(dict.fromkeys(list(p.get("barriers") or []) + list(p.get("barriers_from_text") or [])))
    return StudentCtx(
        id=student_id, campus=s["campus"], language=p.get("language") or s["language"] or "en",
        home_area=s["home_area"], housing=s["housing"], focus=p.get("focus_dimension"), barriers=barriers,
        windows=windows, target_rung=p.get("social_rung") or 1, free_only=p.get("free_only", True) if p else True,
        declined=frozenset(r["item_id"] for r in declined), committed=frozenset(r["item_id"] for r in committed),
        care_first=care_first,
    )


def helped_stats(conn, ctx: StudentCtx, now: datetime) -> HelpedStats:
    """Cohort = same campus and housing. Only feedback from suggestions shown on or before simulated now."""
    rows = conn.execute(
        """SELECT coalesce(i.series_key, i.id) AS key, count(*) FILTER (WHERE f.helped >= 4) AS helped, count(*) AS n
           FROM feedback f JOIN commitments c ON c.id = f.commitment_id
           JOIN recommendations r ON r.id = c.recommendation_id
           JOIN students s ON s.id = c.student_id
           JOIN kb_items i ON i.id = c.item_id
           WHERE f.went AND NOT s.sandbox AND s.campus = %s AND s.housing IS NOT DISTINCT FROM %s AND r.shown_on <= %s AND s.id <> %s
           GROUP BY 1""",
        (ctx.campus, ctx.housing, now.astimezone(NY).date(), ctx.id),
    ).fetchall()
    tot_h = sum(r["helped"] for r in rows)
    tot_n = sum(r["n"] for r in rows)
    prior = (tot_h / tot_n) if tot_n >= 20 else 0.6
    campus = {"newark": "Newark", "camden": "Camden", "new_brunswick": "New Brunswick"}.get(ctx.campus, "")
    housing = {"commuter": "commuters", "resident": "residents"}.get(ctx.housing or "", "students")
    return HelpedStats(by_key={r["key"]: (r["helped"], r["n"]) for r in rows}, prior=round(prior, 3),
                       cohort_label=f"{campus} {housing}".strip())


def memory_facts(conn, student_id: str) -> list[MemoryFact]:
    rows = conn.execute("SELECT id, kind, key, statement, confidence FROM student_memory WHERE student_id = %s ORDER BY id",
                        (student_id,)).fetchall()
    return [MemoryFact(id=r["id"], kind=r["kind"], key=r["key"], statement=r["statement"], confidence=float(r["confidence"])) for r in rows]


def going_count(conn, item_id: str) -> int:
    # sandbox (table-tour) students never count toward social proof
    r = conn.execute("""SELECT count(*) AS n FROM commitments c JOIN students s ON s.id = c.student_id
                        WHERE c.item_id = %s AND c.status IN ('planned','went') AND NOT s.sandbox""", (item_id,)).fetchone()
    return int(r["n"])
