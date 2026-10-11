"""Notification rules, the dispatcher, and skip-ahead. Notifications are rows; sending is idempotent.

Every decision reads the simulated clock passed in. Copy comes from templates only (lock-screen safe)."""
import logging
from datetime import date, datetime, time, timedelta
from functools import lru_cache

import yaml

from app import clock
from app.clock import NY
from app.llm import templates
from app.loop import push
from app.models.loop import FiredNotification
from config.settings import CONFIG_DIR

log = logging.getLogger("compass.notify")


@lru_cache
def cfg() -> dict:
    return yaml.safe_load((CONFIG_DIR / "notifications.yaml").read_text(encoding="utf-8"))


def _t(s: str) -> time:
    return time.fromisoformat(s)


def in_quiet(dt: datetime) -> bool:
    q = cfg()["quiet_hours"]
    t = dt.astimezone(NY).time()
    qs, qe = _t(q["start"]), _t(q["end"])
    return t >= qs or t < qe if qs > qe else qs <= t < qe


def after_quiet(dt: datetime) -> datetime:
    """Move a time out of quiet hours to the next quiet-hours end."""
    if not in_quiet(dt):
        return dt
    dt = dt.astimezone(NY)
    end = _t(cfg()["quiet_hours"]["end"])
    day = dt.date() if dt.time() < end else dt.date() + timedelta(days=1)
    return datetime.combine(day, end, tzinfo=NY)


def is_banned(text: str) -> bool:
    low = text.lower()
    import re
    return any(re.search(rf"\b{re.escape(w)}\b", low) for w in cfg()["banned_words"])


def _insert(c, student_id: str, kind: str, title: str, body: str, link: str, send_at: datetime, commitment_id: int | None = None) -> int | None:
    assert not is_banned(title + " " + body), "notification copy must be lock-screen safe"
    r = c.execute(
        """INSERT INTO notifications (student_id, channel, kind, title, body, deep_link, send_at, status, commitment_id)
           VALUES (%s, 'push', %s, %s, %s, %s, %s, 'scheduled', %s)
           ON CONFLICT (commitment_id, kind) WHERE commitment_id IS NOT NULL DO NOTHING RETURNING id""",
        (student_id, kind, title, body, link, send_at, commitment_id)).fetchone()
    return r["id"] if r else None


def schedule_for_commitment(c, student_id: str, commitment_id: int, item: dict, now: datetime, lang: str, care_first: bool) -> tuple[datetime | None, datetime | None]:
    """Reminder before start (skipped if it would land in quiet hours after the start, or in the past) and one follow-up."""
    n = cfg()
    reminder_at = followup_at = None
    f = {"title": item["title"], "venue": item.get("venue")}
    if item.get("starts_at"):
        start = item["starts_at"]
        r = start - timedelta(minutes=n["reminder_minutes_before"])
        if in_quiet(r):
            r2 = after_quiet(r)
            r = r2 if r2 < start else None
        if r is not None and r > now:
            title, body = templates.reminder(f, care_first, lang)
            _insert(c, student_id, "reminder", title, body, f"/plan/{commitment_id}", r, commitment_id)
            reminder_at = r
        end = item.get("ends_at") or start + timedelta(hours=1)
        followup_at = after_quiet(end + timedelta(minutes=n["followup_after_end_minutes"]))
    else:
        d = now.astimezone(NY).date() + timedelta(days=n["followup_untimed_days"])
        followup_at = datetime.combine(d, time(17, 0), tzinfo=NY)
    title, body = templates.followup(f, lang)
    _insert(c, student_id, "followup", title, body, f"/followup/{commitment_id}", followup_at, commitment_id)
    return reminder_at, followup_at


def fresh_start_days(after: datetime, before: datetime) -> list[datetime]:
    """Weekly-pick moments (Monday 10:00, the 1st of the month, week after midterms) in (after, before]."""
    w = cfg()["weekly_pick"]
    out = []
    d = after.astimezone(NY).date()
    extra = {date.fromisoformat(x) for x in cfg()["fresh_start_extra_dates"]}
    while d <= before.astimezone(NY).date():
        if d.weekday() == w["weekday"] or d.day == 1 or d in extra:
            t = datetime.combine(d, _t(w["time"]), tzinfo=NY)
            if after < t <= before:
                out.append(t)
        d += timedelta(days=1)
    return out


def ensure_fresh_start_nudges(c, student_id: str, after: datetime, horizon: datetime) -> None:
    """Create weekly-pick and retake nudges for upcoming fresh starts, lazily and at most once each."""
    p = c.execute("SELECT focus_dimension, language FROM profiles WHERE student_id = %s", (student_id,)).fetchone()
    if not p or not p["focus_dimension"]:
        return
    if c.execute("SELECT 1 FROM commitments WHERE student_id = %s AND status = 'planned'", (student_id,)).fetchone():
        return  # they already have their step; the weekly pick and retake nudge wait for the next fresh start
    lang = p["language"] or "en"
    rcfg = cfg()["retake"]
    for t in fresh_start_days(after, horizon):
        exists = c.execute("SELECT 1 FROM notifications WHERE student_id = %s AND kind = 'weekly_pick' AND send_at = %s",
                           (student_id, t)).fetchone()
        if not exists:
            title, body = (("Tu próximo paso de la semana está listo", "Uno solo, elegido para tu semana.") if lang == "es"
                           else ("Your next step for this week is ready", "Just one, picked for your week."))
            _insert(c, student_id, "weekly_pick", title, body, "/next", t)
        last_take = c.execute("SELECT max(taken_on) AS d FROM inventory_takes WHERE student_id = %s AND taken_on <= %s",
                              (student_id, t.date())).fetchone()["d"]
        if last_take and (t.date() - last_take).days >= rcfg["min_days_since_take"]:
            recent = c.execute(
                """SELECT count(*) AS n, max(send_at) AS last FROM notifications WHERE student_id = %s AND kind = 'retake_nudge'
                   AND send_at > %s""", (student_id, datetime.combine(last_take, time(0), tzinfo=NY))).fetchone()
            too_soon = recent["last"] and (t - recent["last"]).days < rcfg["min_days_between"]
            if recent["n"] < rcfg["max_unanswered"] and not too_soon:
                title, body = (("Nuevo comienzo", "Si quieres, vuelve a hacer el inventario en MyRutgers y mira tu avance.") if lang == "es"
                               else ("Fresh start this week", "If you want, retake the inventory in MyRutgers and see what's changed."))
                _insert(c, student_id, "retake_nudge", title, body, "https://my.rutgers.edu", t + timedelta(minutes=1))


def _week_bounds(dt: datetime) -> tuple[datetime, datetime]:
    d = dt.astimezone(NY).date()
    start = datetime.combine(d - timedelta(days=d.weekday()), time(0), tzinfo=NY)
    return start, start + timedelta(days=7)


def dispatch_due(c, student_id: str | None, now: datetime) -> list[FiredNotification]:
    """Send everything due at simulated `now` (oldest first). Budget and quiet hours enforced here too."""
    q = """SELECT * FROM notifications WHERE status = 'scheduled' AND send_at <= %s"""
    args: list = [now]
    if student_id:
        q += " AND student_id = %s"
        args.append(student_id)
    rows = c.execute(q + " ORDER BY send_at, id FOR UPDATE SKIP LOCKED", args).fetchall()
    fired = []
    maxw = cfg()["max_pushes_per_week"]
    for n in rows:
        ws, we = _week_bounds(n["send_at"])
        sent = c.execute(
            "SELECT count(*) AS k FROM notifications WHERE student_id = %s AND delivered = 'push' AND send_at >= %s AND send_at < %s",
            (n["student_id"], ws, we)).fetchone()["k"]
        if n["commitment_id"]:
            st = c.execute("SELECT status FROM commitments WHERE id = %s", (n["commitment_id"],)).fetchone()
            if st and st["status"] in ("cancelled",) or (st and n["kind"] == "followup" and st["status"] in ("went", "missed")):
                c.execute("UPDATE notifications SET status = 'cancelled' WHERE id = %s", (n["id"],))
                continue
        if sent >= maxw:
            delivered, status = "held_budget", "held_budget"
        else:
            # Uses the push channel (budgeted) even if the student has no device subscribed yet; the inbox shows it too.
            push.send_to_student(c, n["student_id"], {"title": n["title"], "body": n["body"], "url": n["deep_link"], "tag": f"compass-{n['id']}"})
            delivered, status = "push", "sent"
        c.execute("UPDATE notifications SET status = %s, delivered = %s, sent_at = %s WHERE id = %s", (status, delivered, now, n["id"]))
        fired.append(FiredNotification(id=n["id"], kind=n["kind"], title=n["title"], body=n["body"], deep_link=n["deep_link"],
                                       send_at=n["send_at"], delivered=delivered, commitment_id=n["commitment_id"]))
    return fired


def skip_ahead(c, ctx, previous: datetime, to: str) -> tuple[list[FiredNotification], datetime]:
    target = clock.parse_target(to, previous)
    sid = ctx.student_id
    if sid:
        ensure_fresh_start_nudges(c, sid, previous, (target or previous) + timedelta(days=8))
    if target is None:  # next_due
        if not sid:
            return [], previous
        r = c.execute("SELECT min(send_at) AS t FROM notifications WHERE student_id = %s AND status = 'scheduled' AND send_at > %s",
                      (sid, previous)).fetchone()
        if not r["t"]:
            return [], previous
        target = clock.to_ny(r["t"])
    if target < previous:
        target = previous
    clock.set_session(c, ctx.sid, target)
    fired = dispatch_due(c, sid, target) if sid else []
    return fired, target


def tick() -> None:
    """Background heartbeat: dispatch anything due for active demo sessions at their own simulated time."""
    from app.db import conn
    with conn() as c:
        if not c.execute("SELECT pg_try_advisory_xact_lock(4243) AS ok").fetchone()["ok"]:
            return
        from app.services.demo import sweep_sandboxes
        sweep_sandboxes(c)
        sessions = c.execute(
            """SELECT DISTINCT ON (student_id) student_id, sim_now FROM demo_sessions
               WHERE student_id IS NOT NULL AND sim_now IS NOT NULL ORDER BY student_id, created_at DESC""").fetchall()
        for s in sessions:
            dispatch_due(c, s["student_id"], clock.to_ny(s["sim_now"]))
