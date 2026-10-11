from fastapi import APIRouter, Depends, Response

from app import auth
from app.auth import SessionCtx, session
from app.models.demo import (
    ClockRequest, ForceTemplatesRequest, PersonasResponse, ResetResponse, SessionRequest,
    SessionResponse, SkipAheadRequest, SkipAheadResponse,
)
from app.routes._serve import serve
from app.services import demo as svc

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/session", response_model=SessionResponse)
def new_session(body: SessionRequest, response: Response):
    ctx = auth.issue(body.persona, sandbox=body.sandbox and body.persona != "staff")
    return svc.start_session(ctx, body.now, response)


@router.get("/personas", response_model=PersonasResponse)
def personas(response: Response):
    return serve(None, "personas", response, svc.personas, persona="_shared")


@router.post("/clock", response_model=SessionResponse)
def set_clock(body: ClockRequest, response: Response, ctx: SessionCtx = Depends(session)):
    return serve(ctx, "session", response, lambda: svc.set_clock(ctx, body.now))


@router.post("/skip-ahead", response_model=SkipAheadResponse)
def skip_ahead(body: SkipAheadRequest, response: Response, ctx: SessionCtx = Depends(session)):
    return serve(ctx, "skip_ahead", response, lambda: svc.skip_ahead(ctx, body.to))


@router.post("/reset", response_model=ResetResponse)
def reset(response: Response):
    return serve(None, "reset", response, svc.reset, persona="_shared")


@router.post("/force-templates", response_model=ResetResponse, summary="Stage switch: skip all model calls")
def force_templates(body: ForceTemplatesRequest, response: Response):
    return svc.force_templates(body.on)
