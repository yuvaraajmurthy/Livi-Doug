"""Simulated clock. Every time-based decision reads clock.now(); nothing calls datetime.now() directly.

Per-session clock rows override the global clock row. All values are America/New_York aware.
"""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from config.settings import get_settings

NY = ZoneInfo("America/New_York")


def default_now() -> datetime:
    return datetime.fromisoformat(get_settings().default_now).astimezone(NY)


def to_ny(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=NY)
    return dt.astimezone(NY)


def now(conn, sid: str | None) -> datetime:
    if sid:
        row = conn.execute("SELECT sim_now FROM demo_sessions WHERE sid = %s", (sid,)).fetchone()
        if row and row["sim_now"]:
            return to_ny(row["sim_now"])
    row = conn.execute("SELECT sim_now FROM app_clock WHERE id = 1").fetchone()
    return to_ny(row["sim_now"]) if row else default_now()


def set_session(conn, sid: str, dt: datetime) -> datetime:
    dt = to_ny(dt)
    conn.execute("UPDATE demo_sessions SET sim_now = %s WHERE sid = %s", (dt, sid))
    return dt


_REL = re.compile(r"^\+(\d+)([mhdw])$")


def parse_target(to: str, current: datetime) -> datetime | None:
    """'+2d', '+3h', '+30m', '+1w' or an ISO datetime. Returns None for 'next_due' (caller resolves)."""
    to = (to or "").strip()
    if to == "next_due":
        return None
    m = _REL.match(to)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n), "w": timedelta(weeks=n)}[unit]
        return current + delta
    return to_ny(datetime.fromisoformat(to))
