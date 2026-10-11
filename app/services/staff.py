"""Staff Pulse. Every query runs as compass_staff_ro, which can only call the suppression functions."""
import json
from datetime import date
from functools import lru_cache

from app import clock
from app.auth import SessionCtx
from app.db import conn
from app.models.staff import (
    CalendarOverlay, Dip, DipsResponse, FunnelResponse, FunnelRow, GapRow, GapsResponse, RetakeRow, RetakesResponse,
    StaffFilters, WeeklyPoint, WeeklyResponse,
)
from config.settings import ROOT

CAMPUS_LABEL = {"camden": "Camden", "newark": "Newark", "new_brunswick": "New Brunswick"}


@lru_cache
def overlays() -> list[CalendarOverlay]:
    cal = json.loads((ROOT / "handoff" / "data" / "out" / "academic_calendar_fall2026.json").read_text(encoding="utf-8"))
    src = "Rutgers academic calendar (fall 2026)"
    d = date.fromisoformat
    return [
        CalendarOverlay(label="Classes begin", start=d(cal["fall_begins"]), end=d(cal["fall_begins"]), approximate=False, source=src),
        CalendarOverlay(label="Midterms (approximate)", start=d(cal["midterm_window_APPROXIMATE"][0]), end=d(cal["midterm_window_APPROXIMATE"][1]),
                        approximate=True, source="Assumption: midterms are not on the registrar calendar"),
        CalendarOverlay(label="Thanksgiving recess", start=d(cal["thanksgiving_recess"][0]), end=d(cal["thanksgiving_recess"][1]), approximate=False, source=src),
        CalendarOverlay(label="Classes end", start=d(cal["classes_end"]), end=d(cal["classes_end"]), approximate=False, source=src),
        CalendarOverlay(label="Reading days", start=d(cal["reading_days"][0]), end=d(cal["reading_days"][1]), approximate=False, source=src),
        CalendarOverlay(label="Final exams", start=d(cal["final_exams"][0]), end=d(cal["final_exams"][1]), approximate=False, source=src),
    ]


def overlay_for(week: date) -> str | None:
    from datetime import timedelta
    end = week + timedelta(days=6)
    for o in overlays():
        if o.start <= end and o.end >= week and o.label != "Classes begin":
            return o.label
    return None


def _q(sql: str, args: tuple) -> list[dict]:
    with conn() as c:
        c.execute("SET LOCAL ROLE compass_staff_ro")
        rows = c.execute(sql, args).fetchall()
        c.execute("RESET ROLE")
        return rows


def _now(ctx):
    with conn() as c:
        return clock.now(c, ctx.sid)


def funnel(ctx: SessionCtx, f: StaffFilters) -> FunnelResponse:
    rows = _q("SELECT * FROM staff_funnel(%s, %s, %s, %s, %s)", (f.campus, f.dimension, f.level, f.first_gen, f.housing))
    ok = [r for r in rows if not r["suppressed"]]
    out = []
    for r in ok:
        out.append(FunnelRow(campus=r["campus"], dimension=r["dimension"], students=r["students"], suggested=r["suggested"],
                             committed=r["committed"], with_friend=r["with_friend"], attended=r["attended"], helped=r["helped"],
                             commit_rate=round(r["committed"] / r["suggested"], 3) if r["suggested"] else 0.0,
                             attend_rate=round(r["attended"] / r["committed"], 3) if r["committed"] else 0.0,
                             helped_rate=round(r["helped"] / r["attended"], 3) if r["attended"] else 0.0))
    totals = None
    if out:
        t = {k: sum(getattr(x, k) for x in out) for k in ("students", "suggested", "committed", "with_friend", "attended", "helped")}
        totals = FunnelRow(campus=f.campus or "new_brunswick", dimension=f.dimension or "social", **t,
                           commit_rate=round(t["committed"] / t["suggested"], 3) if t["suggested"] else 0.0,
                           attend_rate=round(t["attended"] / t["committed"], 3) if t["committed"] else 0.0,
                           helped_rate=round(t["helped"] / t["attended"], 3) if t["attended"] else 0.0)
    return FunnelResponse(synthetic=True, now=_now(ctx), filters=f, suppressed_groups=len(rows) - len(ok), rows=out, totals=totals)


def gaps(ctx: SessionCtx, f: StaffFilters) -> GapsResponse:
    rows = _q("SELECT * FROM staff_gaps(%s, %s, %s, %s, %s)", (f.campus, f.dimension, f.level, f.first_gen, f.housing))
    ok = [r for r in rows if not r["suppressed"]]
    out = [GapRow(campus=r["campus"], dimension=r["dimension"], low_students=r["low_students"], items=r["items"],
                  low_students_per_item=float(r["low_students_per_item"])) for r in ok]
    head = ""
    if out:
        top = out[0]
        head = (f"{CAMPUS_LABEL.get(top.campus, top.campus)} has {round(top.low_students_per_item)} students with low {top.dimension} "
                f"scores for every {top.dimension} event or resource listed there.")
    return GapsResponse(synthetic=True, now=_now(ctx), filters=f, suppressed_groups=len(rows) - len(ok), rows=out, headline=head)


def weekly(ctx: SessionCtx, f: StaffFilters) -> WeeklyResponse:
    rows = _q("SELECT * FROM staff_weekly(%s, %s, %s, %s, %s)", (f.campus, f.dimension, f.level, f.first_gen, f.housing))
    ok = [r for r in rows if not r["suppressed"]]
    pts = [WeeklyPoint(campus=r["campus"], dimension=r["dimension"], week=r["week"], avg_score=float(r["avg_score"]), n=r["n"]) for r in ok]
    return WeeklyResponse(synthetic=True, now=_now(ctx), filters=f, suppressed_groups=len(rows) - len(ok), points=pts, overlays=overlays())


def dips(ctx: SessionCtx, f: StaffFilters, threshold: float | None) -> DipsResponse:
    thr = threshold or 0.15
    rows = _q("SELECT * FROM staff_dips(%s::numeric, %s, %s, %s, %s, %s)", (thr, f.campus, f.dimension, f.level, f.first_gen, f.housing))
    out = [Dip(campus=r["campus"], dimension=r["dimension"], week=r["week"], avg_score=float(r["avg_score"]),
               trailing_avg=float(r["trailing_avg"]), drop=float(r["drop"]), n=r["n"], overlay=overlay_for(r["week"])) for r in rows]
    return DipsResponse(synthetic=True, now=_now(ctx), filters=f, suppressed_groups=0, threshold=thr, dips=out, overlays=overlays())


def retakes(ctx: SessionCtx, f: StaffFilters) -> RetakesResponse:
    rows = _q("SELECT * FROM staff_retakes(%s, %s, %s, %s)", (f.campus, f.level, f.first_gen, f.housing))
    ok = [r for r in rows if not r["suppressed"]]
    out = [RetakeRow(campus=r["campus"], users=r["users"], users_retook=r["users_retook"], users_rate=round(r["users_retook"] / r["users"], 3),
                     non_users=r["non_users"], non_users_retook=r["non_users_retook"],
                     non_users_rate=round(r["non_users_retook"] / r["non_users"], 3)) for r in ok]
    return RetakesResponse(synthetic=True, now=_now(ctx), filters=f, suppressed_groups=len(rows) - len(ok), rows=out)
