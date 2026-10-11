from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from app.auth import SessionCtx, staff_session
from app.models.common import Campus, Dimension
from app.models.staff import (
    DipsResponse, FunnelResponse, StaffAskRequest, StaffAskResponse, GapsResponse, RetakesResponse, StaffFilters, WeeklyResponse,
)
from app.routes._serve import serve
from app.services import staff as svc

router = APIRouter(prefix="/staff", tags=["staff"])


def filters(
    campus: Campus | None = None,
    dimension: Dimension | None = None,
    level: Literal["undergrad", "grad"] | None = None,
    first_gen: bool | None = None,
    housing: Literal["resident", "commuter"] | None = None,
) -> StaffFilters:
    return StaffFilters(campus=campus, dimension=dimension, level=level, first_gen=first_gen, housing=housing)


@router.get("/funnel", response_model=FunnelResponse)
def funnel(response: Response, f: StaffFilters = Depends(filters), ctx: SessionCtx = Depends(staff_session)):
    return serve(ctx, "staff_funnel", response, lambda: svc.funnel(ctx, f))


@router.get("/gaps", response_model=GapsResponse)
def gaps(response: Response, f: StaffFilters = Depends(filters), ctx: SessionCtx = Depends(staff_session)):
    return serve(ctx, "staff_gaps", response, lambda: svc.gaps(ctx, f))


@router.get("/weekly", response_model=WeeklyResponse)
def weekly(response: Response, f: StaffFilters = Depends(filters), ctx: SessionCtx = Depends(staff_session)):
    return serve(ctx, "staff_weekly", response, lambda: svc.weekly(ctx, f))


@router.get("/dips", response_model=DipsResponse)
def dips(response: Response, threshold: float | None = Query(None, ge=0.01, le=1.0),
         f: StaffFilters = Depends(filters), ctx: SessionCtx = Depends(staff_session)):
    return serve(ctx, "staff_dips", response, lambda: svc.dips(ctx, f, threshold))


@router.get("/retakes", response_model=RetakesResponse)
def retakes(response: Response, f: StaffFilters = Depends(filters), ctx: SessionCtx = Depends(staff_session)):
    return serve(ctx, "staff_retakes", response, lambda: svc.retakes(ctx, f))


@router.post("/ask", response_model=StaffAskResponse, tags=["p2"], summary="Ask the data: NL -> read-only SQL over suppressed aggregates (query shown)")
def staff_ask(body: StaffAskRequest, response: Response, ctx: SessionCtx = Depends(staff_session)):
    from app.ask.staff_sql import ask
    from app import clock
    from app.db import conn
    with conn() as c:
        now = clock.now(c, ctx.sid)
    return StaffAskResponse(synthetic=True, now=now, **ask(body.question[:400], now.date().isoformat()))
