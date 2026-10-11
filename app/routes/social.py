from fastapi import APIRouter, Depends, Response

from app.auth import SessionCtx, student_session
from app.models.social import PulseResponse, SameHere, WinRequest, WinResult
from app.routes._serve import serve
from app.services import social as svc

router = APIRouter(tags=["social"])


@router.get("/pulse", response_model=PulseResponse)
def pulse(response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "pulse", response, lambda: svc.pulse(ctx))


@router.post("/wins", response_model=WinResult)
def post_win(body: WinRequest, response: Response, ctx: SessionCtx = Depends(student_session)):
    from app.safety.lexicon import quick_crisis
    key = "win_crisis" if quick_crisis(body.text) else "win_accepted"
    return serve(ctx, key, response, lambda: svc.post_win(ctx, body))


@router.post("/wins/{win_id}/same-here", response_model=SameHere)
def same_here(win_id: str, response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "same_here", response, lambda: svc.same_here(ctx, win_id))
