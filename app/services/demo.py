"""Demo controls: sessions, simulated clock, skip-ahead, reset."""
import time
from datetime import datetime

from fastapi import Response
from psycopg import sql

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
                if ctx.sandbox and ctx.student_id:
                    from app.auth import PERSONA_STUDENT
                    clone_persona(c, PERSONA_STUDENT[ctx.persona], ctx.student_id)
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


# Sandbox clones ------------------------------------------------------------------------------------------------------
_COLS: dict[str, list[str]] = {}


def _cols(c, table: str) -> list[str]:
    if table not in _COLS:
        rows = c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s "
                         "AND table_schema = current_schema() ORDER BY ordinal_position", (table,)).fetchall()
        _COLS[table] = [r["column_name"] for r in rows]
    return _COLS[table]


def _copy(c, table: str, key: str, base_id: str, clone_id: str, skip: tuple[str, ...] = ("id",),
          override: dict[str, object] | None = None) -> None:
    """INSERT INTO table (cols) SELECT cols FROM table WHERE key = base_id, with key := clone_id and overrides."""
    override = {key: clone_id, **(override or {})}
    cols = [col for col in _cols(c, table) if col not in skip or col in override]
    select = [sql.Placeholder() if col in override else sql.Identifier(col) for col in cols]
    params = [override[col] for col in cols if col in override] + [base_id]
    c.execute(sql.SQL("INSERT INTO {t} ({cols}) SELECT {sel} FROM {t} WHERE {k} = %s").format(
        t=sql.Identifier(table), cols=sql.SQL(", ").join(map(sql.Identifier, cols)),
        sel=sql.SQL(", ").join(select), k=sql.Identifier(key)), params)


def clone_persona(c, base_id: str, clone_id: str) -> None:
    """Copy a demo persona (identity, profile, consents, memory, inventory takes and scores) to a private sandbox id."""
    _copy(c, "students", "id", base_id, clone_id, skip=(), override={"sandbox": True, "sandbox_created": datetime.now().astimezone()})
    for table in ("profiles", "consents", "student_memory"):
        _copy(c, table, "student_id", base_id, clone_id)
    takes = c.execute("SELECT id, take_no, taken_on, source, total FROM inventory_takes WHERE student_id = %s",
                      (base_id,)).fetchall()
    for t in takes:  # dimension_scores hang off take ids, so map old -> new per take
        new_id = c.execute("INSERT INTO inventory_takes (student_id, take_no, taken_on, source, total) "
                           "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                           (clone_id, t["take_no"], t["taken_on"], t["source"], t["total"])).fetchone()["id"]
        c.execute("INSERT INTO dimension_scores (take_id, dimension, score) "
                  "SELECT %s, dimension, score FROM dimension_scores WHERE take_id = %s", (new_id, t["id"]))


def sweep_sandboxes(c, max_age_hours: int = 6) -> int:
    return c.execute("DELETE FROM students WHERE sandbox AND sandbox_created < now() - make_interval(hours => %s)",
                     (max_age_hours,)).rowcount
