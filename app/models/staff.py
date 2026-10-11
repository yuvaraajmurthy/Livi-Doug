from datetime import date
from typing import Literal

from app.models.common import Campus, Dimension, Envelope, Model


class StaffFilters(Model):
    campus: Campus | None = None
    dimension: Dimension | None = None
    level: Literal["undergrad", "grad"] | None = None
    first_gen: bool | None = None
    housing: Literal["resident", "commuter"] | None = None


class StaffEnvelope(Envelope):
    filters: StaffFilters
    suppressed_groups: int
    min_group_size: int = 10


class FunnelRow(Model):
    campus: Campus
    dimension: Dimension
    students: int
    suggested: int
    committed: int
    with_friend: int
    attended: int
    helped: int
    commit_rate: float
    attend_rate: float
    helped_rate: float


class FunnelResponse(StaffEnvelope):
    rows: list[FunnelRow]
    totals: FunnelRow | None


class GapRow(Model):
    campus: Campus
    dimension: Dimension
    low_students: int
    items: int
    low_students_per_item: float


class GapsResponse(StaffEnvelope):
    rows: list[GapRow]
    headline: str


class CalendarOverlay(Model):
    label: str
    start: date
    end: date
    approximate: bool
    source: str


class WeeklyPoint(Model):
    campus: Campus
    dimension: Dimension
    week: date
    avg_score: float
    n: int


class WeeklyResponse(StaffEnvelope):
    points: list[WeeklyPoint]
    overlays: list[CalendarOverlay]


class Dip(Model):
    campus: Campus
    dimension: Dimension
    week: date
    avg_score: float
    trailing_avg: float
    drop: float
    n: int
    overlay: str | None


class DipsResponse(StaffEnvelope):
    threshold: float
    dips: list[Dip]
    overlays: list[CalendarOverlay]


class RetakeRow(Model):
    campus: Campus
    users: int
    users_retook: int
    users_rate: float
    non_users: int
    non_users_retook: int
    non_users_rate: float


class RetakesResponse(StaffEnvelope):
    rows: list[RetakeRow]
