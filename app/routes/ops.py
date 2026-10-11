from fastapi import APIRouter, Depends, Response

from app.auth import SessionCtx, student_session
from app.models.demo import Health
from app.models.loop import SubscriptionRequest, SubscriptionResult, VapidKey
from app.routes._serve import serve
from app.services import ops as svc

router = APIRouter()


@router.get("/health", response_model=Health, tags=["ops"])
def health(deep: bool = False):
    return svc.health(deep)


@router.get("/push/vapid-key", response_model=VapidKey, tags=["push"])
def vapid_key():
    return svc.vapid_key()


@router.post("/push/subscriptions", response_model=SubscriptionResult, tags=["push"])
def subscribe(body: SubscriptionRequest, response: Response, test: bool = False, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "subscription", response, lambda: svc.subscribe(ctx, body, test))


@router.delete("/push/subscriptions", response_model=SubscriptionResult, tags=["push"])
def unsubscribe(endpoint: str, response: Response, ctx: SessionCtx = Depends(student_session)):
    return serve(ctx, "subscription", response, lambda: svc.unsubscribe(ctx, endpoint))
