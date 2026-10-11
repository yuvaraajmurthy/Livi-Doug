"""Demo controls: sessions, simulated clock, skip-ahead, reset."""
import time
from datetime import datetime

from fastapi import Response

from app import clock
from app.auth import SessionCtx
from app.db import DB_ERRORS, conn
from app.models.demo import PersonaInfo, PersonasResponse, ResetResponse, SessionResponse, SkipAheadResponse
from config.settings import get_settings

PERSONAS = [
    PersonaInfo(key="andre", name="Andre", campus="newark", role_in_demo="Main: Newark commuter, first-gen, works afternoons. Social is his growth area."),
    PersonaInfo(key="priya", name="Priya", campus="new_brunswick", role_in_demo="Busch sophomore: sleep is low because of Calc II. Gets real tutoring."),
    PersonaInfo(key="taylor", name="Taylor", campus="new_brunswick", role_in_demo="Care-first: a person comes first, events are not pushed."),
    PersonaInfo(key="sofia", name="Sofia", campus="camden", role_in_demo="Camden grad, works full time, prefers Spanish. Thin financial supply."),
    PersonaInfo(key="jordan", name="Jordan", campus="new_brunswick", role_in_demo="Livingston first-year, lonely, athletic. Residence-hall challenge."),
    PersonaInfo(key="staff", name="ScarletWell staff", campus=None, role_in_demo="Staff Pulse: aggregates only, groups under 10 hidden."),
]


def personas() -> PersonasResponse:
    return PersonasResponse(synthetic=True, now=clock.default_now(), personas=PERSONAS)


def start_session(ctx: SessionCtx, start: datetime | None, response: Response) -> SessionResponse:
    sim_now = clock.to_ny(start) if start else None
    if get_settings().mode == "live":
        try:
            with conn() as c:
                if sim_now is None:
                    sim_now = clock.now(c, None)
                c.execute(
                    "INSERT INTO demo_sessions (sid, persona, student_id, sim_now) VALUES (%s, %s, %s, %s)",
                    (ctx.sid, ctx.persona, ctx.student_id, sim_now),
                )
        except DB_ERRORS:
            response.headers["X-Compass-Fallback"] = "fixture"
    return SessionResponse(
        synthetic=True, now=sim_now or clock.default_now(), token=ctx.token, persona=ctx.persona,
        role=ctx.role, student_id=ctx.student_id,
    )


def set_clock(ctx: SessionCtx, dt: datetime) -> SessionResponse:
    from app.loop.notify import dispatch_due
    with conn() as c:
        new = clock.set_session(c, ctx.sid, dt)
        if ctx.student_id:
            dispatch_due(c, ctx.student_id, new)
    return SessionResponse(synthetic=True, now=new, token=ctx.token, persona=ctx.persona, role=ctx.role, student_id=ctx.student_id)


def skip_ahead(ctx: SessionCtx, to: str) -> SkipAheadResponse:
    from app.loop.notify import skip_ahead as _skip
    with conn() as c:
        previous = clock.now(c, ctx.sid)
        fired, new_now = _skip(c, ctx, previous, to)
    return SkipAheadResponse(synthetic=True, now=new_now, previous_now=previous, fired=fired)


def reset() -> ResetResponse:
    from db.reset import reset_demo
    t = time.perf_counter()
    reset_demo()
    from app.services.prewarm import run_in_background
    run_in_background()
    return ResetResponse(synthetic=True, now=clock.default_now(), ok=True, seconds=round(time.perf_counter() - t, 2))


def force_templates(on: bool) -> ResetResponse:
    get_settings().force_templates = on
    return ResetResponse(synthetic=True, now=clock.default_now(), ok=True, seconds=0.0)
