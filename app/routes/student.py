from fastapi import APIRouter, Depends, Response

from app.auth import SessionCtx, student_session
from app.models.common import CrisisResponse
from app.models.student import (
    BarrierMeta, CardResponse, DeclineRequest, DeleteResult, FocusRequest, FocusResponse,
    InboxResponse, MapResponse, MemoryList, NextResponse,
)
from app.routes._serve import serve
from app.services import student as svc

router = APIRouter(tags=["student"])


@router.get("/meta/barriers", response_model=BarrierMeta, tags=["meta"])
def barrier_meta():
    return svc.barrier_meta()


@router.get("/me/map", response_model=MapResponse)
def me_map(response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "me_map", response, lambda: svc.get_map(ctx))


@router.post("/me/focus", response_model=FocusResponse, responses={200: {"description": "Profile, or the fixed crisis response if typed text triggered the safety check."}})
def me_focus(body: FocusRequest, response: Response, ctx: SessionCtx = Depends(student_session)):
    key = "me_focus_crisis" if body.text and _looks_crisis_for_fixture(body.text) else "me_focus"
    return serve(ctx, key, response, lambda: svc.set_focus(ctx, body))


@router.get("/me/next", response_model=NextResponse)
def me_next(response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "me_next", response, lambda: svc.get_next(ctx))


@router.post("/me/next/{rec_id}/decline", response_model=NextResponse)
def me_decline(rec_id: int, body: DeclineRequest, response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "me_next_after_decline", response, lambda: svc.decline(ctx, rec_id, body))


@router.get("/me/card", response_model=CardResponse)
def me_card(response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "me_card", response, lambda: svc.get_card(ctx))


@router.get("/me/memory", response_model=MemoryList)
def me_memory(response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "me_memory", response, lambda: svc.list_memory(ctx))


@router.delete("/me/memory/{memory_id}", response_model=DeleteResult)
def me_memory_delete(memory_id: str, response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "delete_result", response, lambda: svc.delete_memory(ctx, memory_id))


@router.delete("/me/memory", response_model=DeleteResult)
def me_memory_delete_all(response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "delete_result", response, lambda: svc.delete_memory(ctx, None))


@router.delete("/me", response_model=DeleteResult, summary="Forget me: delete everything personal")
def forget_me(response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "delete_result", response, lambda: svc.forget_me(ctx))


@router.get("/me/inbox", response_model=InboxResponse)
def me_inbox(response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "me_inbox", response, lambda: svc.inbox(ctx))


def _looks_crisis_for_fixture(text: str) -> bool:
    # Fixture mode only: route crisis-looking text to the crisis fixture. Live mode uses app.safety.
    from app.safety.lexicon import quick_crisis
    return quick_crisis(text)


_ = CrisisResponse  # referenced in OpenAPI via FocusResponse
