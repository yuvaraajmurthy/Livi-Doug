import time

from app.db import DB_ERRORS, conn
from app.models.demo import Health, HealthCheck
from app.models.loop import VapidKey
from config.settings import get_settings


def health(deep: bool = False) -> Health:
    s = get_settings()
    checks: dict[str, HealthCheck] = {}
    if s.mode == "live":
        t = time.perf_counter()
        try:
            with conn() as c:
                c.execute("SELECT 1")
            checks["db"] = HealthCheck(ok=True, latency_ms=round((time.perf_counter() - t) * 1000, 1))
        except DB_ERRORS as exc:
            checks["db"] = HealthCheck(ok=False, detail=type(exc).__name__)
    else:
        checks["db"] = HealthCheck(ok=True, detail="fixture mode")
    if deep:
        from app.llm.bedrock import ping
        checks["bedrock"] = ping()
    else:
        checks["bedrock"] = HealthCheck(ok=s.bedrock_enabled and not s.force_templates,
                                        detail="templates forced" if s.force_templates else "not probed (use ?deep=true)")
    checks["push"] = HealthCheck(ok=bool(s.vapid_public_key), detail=None if s.vapid_public_key else "VAPID not configured")
    status = "ok" if checks["db"].ok else ("degraded" if s.mode == "live" else "ok")
    return Health(status=status, mode=s.mode, version=s.version, checks=checks)


def vapid_key() -> VapidKey:
    return VapidKey(public_key=get_settings().vapid_public_key)


def subscribe(ctx, body, test):
    from app import clock
    from app.loop import push
    from app.models.loop import SubscriptionResult
    with conn() as c:
        now = clock.now(c, ctx.sid)
        c.execute(
            """INSERT INTO push_subscriptions (student_id, endpoint, p256dh, auth) VALUES (%s, %s, %s, %s)
               ON CONFLICT (endpoint) DO UPDATE SET student_id = EXCLUDED.student_id, p256dh = EXCLUDED.p256dh,
                 auth = EXCLUDED.auth, revoked_at = NULL""",
            (ctx.student_id, body.endpoint, body.keys.p256dh, body.keys.auth))
        sent = False
        if test:
            sub = c.execute("SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE endpoint = %s", (body.endpoint,)).fetchone()
            sent = push.send_one(c, sub, {"title": "Compass is set up", "body": "You'll get at most 3 nudges a week.", "url": "/"})
        return SubscriptionResult(synthetic=True, now=now, ok=True, test_sent=sent)


def unsubscribe(ctx, endpoint):
    from app import clock
    from app.models.loop import SubscriptionResult
    with conn() as c:
        now = clock.now(c, ctx.sid)
        c.execute("UPDATE push_subscriptions SET revoked_at = now() WHERE endpoint = %s AND student_id = %s", (endpoint, ctx.student_id))
        return SubscriptionResult(synthetic=True, now=now, ok=True)
