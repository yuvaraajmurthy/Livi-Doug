"""Every student/demo route goes through serve(): live first, fixture on DB failure or in fixture mode."""
import logging
from typing import Any, Callable

from fastapi import Response

from app.auth import SessionCtx
from app.db import DB_ERRORS
from app.fixtures.loader import fixture
from config.settings import get_settings

log = logging.getLogger("compass.serve")


class NotLive(Exception):
    """Raised by a handler whose live path is not available yet; serve() falls back to the fixture."""


def serve(ctx: SessionCtx | None, key: str, response: Response, live: Callable[[], Any], persona: str | None = None) -> Any:
    who = persona or (ctx.persona if ctx else "_shared")
    if get_settings().mode == "fixtures":
        response.headers["X-Compass-Fallback"] = "fixture"
        return fixture(who, key)
    try:
        return live()
    except NotLive:
        response.headers["X-Compass-Fallback"] = "fixture"
        return fixture(who, key)
    except DB_ERRORS as exc:
        log.warning("db unavailable, serving fixture", extra={"route_key": key, "err": type(exc).__name__})
        response.headers["X-Compass-Fallback"] = "fixture"
        return fixture(who, key)
