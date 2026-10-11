from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse

from app.auth import SessionCtx, student_session
from app.models.loop import (
    CommitRequest, CommitResult, FollowupRequest, FollowupResponse, InviteAccepted, InviteView,
)
from app.routes._serve import serve
from app.services import loop as svc

router = APIRouter(tags=["loop"])


@router.post("/commitments", response_model=CommitResult)
def commit(body: CommitRequest, response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "commitment", response, lambda: svc.commit(ctx, body))


@router.get("/commitments/{commitment_id}/ics", response_class=PlainTextResponse,
            responses={200: {"content": {"text/calendar": {}}}})
def commitment_ics(commitment_id: int, t: str):
    """Calendar file. `t` is the invite token (so the link works from a calendar app without auth)."""
    return PlainTextResponse(svc.ics(commitment_id, t), media_type="text/calendar")


@router.get("/invites/{token}", response_model=InviteView, tags=["public"])
def invite_view(token: str, response: Response):
    return serve(None, "invite", response, lambda: svc.invite_view(token), persona="_shared")


@router.post("/invites/{token}", response_model=InviteAccepted, tags=["public"])
def invite_accept(token: str, response: Response):
    return serve(None, "invite_accepted", response, lambda: svc.invite_accept(token), persona="_shared")


@router.post("/followups/{commitment_id}", response_model=FollowupResponse)
def followup(commitment_id: int, body: FollowupRequest, response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "followup", response, lambda: svc.followup(ctx, commitment_id, body))
