"""Compass API: the layer between the Wellness Inventory and the help Rutgers already has."""
import json
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import demo, loop, ops, social, staff, student, voice
from config.settings import get_settings


class JsonFormatter(logging.Formatter):
    """Structured logs. Never log request bodies: they can hold free text."""
    SAFE = ("request_id", "route", "method", "status", "ms", "fallback", "route_key", "err", "model", "purpose", "outcome")

    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": round(record.created, 3), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for k in self.SAFE:
            if hasattr(record, k):
                out[k] = getattr(record, k)
        return json.dumps(out)


def _setup_logging() -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").disabled = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    s = get_settings()
    workers = []
    if s.mode == "live":
        from app.workers import start_workers
        workers = start_workers()
    yield
    for w in workers:
        w.stop()
    from app.db import close_pool
    close_pool()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Compass API",
        version=s.version,
        description=(
            "Backend for Compass (Rutgers Health Hack 2026). Turns Wellness Inventory scores into one next step, "
            "follows up, and feeds Staff Pulse. All data in this prototype is synthetic or labelled sample unless "
            "marked otherwise. Auth: POST /demo/session, then `Authorization: Bearer <token>`. Every response "
            "carries `synthetic` and the simulated `now`. Header `X-Compass-Fallback: fixture|template` marks fallbacks."
        ),
        lifespan=lifespan,
    )
    origins = [o.strip() for o in s.cors_origins.split(",")] if s.cors_origins != "*" else ["*"]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Compass-Fallback", "X-Request-Id"],
    )

    access = logging.getLogger("compass.access")

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        t = time.perf_counter()
        response = await call_next(request)
        ms = round((time.perf_counter() - t) * 1000, 1)
        response.headers["X-Request-Id"] = rid
        route = request.scope.get("route")
        access.info("request", extra={
            "request_id": rid, "method": request.method, "route": getattr(route, "path", request.url.path),
            "status": response.status_code, "ms": ms, "fallback": response.headers.get("X-Compass-Fallback"),
        })
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "message": str(exc.detail)}
        return JSONResponse(detail, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        # Do not echo input back: it can contain free text.
        fields = [".".join(str(p) for p in e.get("loc", [])) + ": " + e.get("msg", "") for e in exc.errors()]
        return JSONResponse({"error": "invalid_request", "message": "; ".join(fields)[:500]}, status_code=422)

    for r in (ops.router, demo.router, student.router, loop.router, social.router, staff.router, voice.router):
        app.include_router(r)
    return app


app = create_app()
