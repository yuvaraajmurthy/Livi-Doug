import time

from app.db import DB_ERRORS, conn
from app.models.demo import Health, HealthCheck
from app.models.loop import VapidKey
from app.routes._serve import NotLive
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
    raise NotLive("subscribe")


def unsubscribe(ctx, endpoint):
    raise NotLive("unsubscribe")
