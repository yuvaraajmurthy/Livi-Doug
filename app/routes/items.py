from fastapi import APIRouter, Depends

from app.auth import SessionCtx, student_session
from app.models.items import ItemDetail
from app.models.loop import CommitResponse
from app.services import items as svc

router = APIRouter(tags=["items"])


@router.get("/items/{item_id}", response_model=ItemDetail, summary="Full details for the event card (map, directions, calendar)")
def item_detail(item_id: str, ctx: SessionCtx = Depends(student_session)):
    return svc.detail(ctx, item_id)


@router.post("/items/{item_id}/remind", response_model=CommitResponse, summary="Plan + reminder for one item (idempotent)")
def item_remind(item_id: str, ctx: SessionCtx = Depends(student_session)):
    return svc.remind(ctx, item_id)
