"""Web push via VAPID (pywebpush). Payload is lock-screen safe copy only. 404/410 revokes the subscription."""
import json
import logging

from config.settings import get_settings

log = logging.getLogger("compass.push")


def send_to_student(c, student_id: str, payload: dict) -> int:
    s = get_settings()
    if not (s.vapid_private_key and s.vapid_public_key):
        return 0
    subs = c.execute("SELECT id, endpoint, p256dh, auth FROM push_subscriptions WHERE student_id = %s AND revoked_at IS NULL",
                     (student_id,)).fetchall()
    sent = 0
    for sub in subs:
        if send_one(c, sub, payload):
            sent += 1
    return sent


def send_one(c, sub: dict, payload: dict) -> bool:
    from pywebpush import WebPushException, webpush
    s = get_settings()
    try:
        webpush(subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=json.dumps(payload), vapid_private_key=s.vapid_private_key,
                vapid_claims={"sub": s.vapid_subject}, ttl=3600, timeout=5)
        return True
    except WebPushException as exc:
        code = getattr(exc.response, "status_code", None)
        if code in (404, 410):
            c.execute("UPDATE push_subscriptions SET revoked_at = now() WHERE id = %s", (sub["id"],))
        log.info("push failed", extra={"outcome": str(code)})
        return False
    except Exception as exc:
        log.info("push failed", extra={"outcome": type(exc).__name__})
        return False
