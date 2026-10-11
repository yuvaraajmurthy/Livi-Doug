from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import Field

from app.models.common import Campus, CrisisResponse, Dimension, Envelope, Model
from app.models.student import RetakeNudge


class Challenge(Model):
    id: str
    title: str
    scope: Literal["all", "campus", "hall", "club"]
    scope_label: str
    dimension: Dimension | None = None
    goal: int
    progress: int
    pct: float
    starts_on: date
    ends_on: date
    rule: str
    yours: bool = Field(description="True if this student's steps count toward it.")
    synthetic: bool


class Win(Model):
    id: str
    text: str
    dimension: Dimension | None
    campus: Campus | None
    same_here: int
    created_at: datetime
    synthetic: bool


class PulseResponse(Envelope):
    challenges: list[Challenge]
    wins: list[Win]
    retake_nudge: RetakeNudge | None = None


class WinRequest(Model):
    text: str = Field(min_length=1, max_length=140)
    dimension: Dimension | None = None


class WinAccepted(Envelope):
    kind: Literal["accepted", "held", "rejected"]
    win_id: str | None
    message: str


WinResult = Annotated[Union[WinAccepted, CrisisResponse], Field(discriminator="kind")]


class SameHere(Envelope):
    win_id: str
    same_here: int
