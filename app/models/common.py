"""Shared contract types. Changing a field here changes the public API: log it in contract/CHANGELOG.md."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Dimension = Literal[
    "emotional", "environmental", "financial", "intellectual",
    "occupational", "physical", "social", "spiritual",
]
DIMENSIONS: tuple[str, ...] = (
    "emotional", "environmental", "financial", "intellectual",
    "occupational", "physical", "social", "spiritual",
)
Campus = Literal["new_brunswick", "newark", "camden", "online", "community"]
Band = Literal["low", "middle", "high"]
Cost = Literal["free", "paid", "unknown"]
Language = Literal["en", "es"]
BarrierChip = Literal[
    "no_time", "dont_know_anyone", "money", "coursework", "not_my_scene",
    "too_far", "low_energy", "not_sure_where",
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Envelope(Model):
    synthetic: bool = Field(description="True when any data in this response is synthetic or a labelled sample.")
    now: datetime = Field(description="Simulated 'now' for this session, America/New_York.")


class CrisisLine(Model):
    id: int
    name: str
    kind: Literal["call", "text", "web", "emergency"]
    contact: str = Field(description="Display text, e.g. 'Call or text 988'.")
    href: str | None = Field(None, description="tel:, sms: or https: link.")
    hours: str
    campus: Literal["all", "new_brunswick", "newark", "camden"]
    language: Literal["en", "es", "any"] = "any"
    verified: bool = Field(description="False until a human has called/checked it. Show a 'verify' badge in non-prod.")


class CrisisResponse(Envelope):
    kind: Literal["crisis"] = "crisis"
    title: str
    message: str = Field(description="Fixed copy from a table. Never model-written.")
    lines: list[CrisisLine]


class SupportOption(Model):
    name: str
    kind: Literal["in_person", "teletherapy", "peer", "phone"]
    contact: str | None = None
    url: str | None = None
    address: str | None = None
    hours: str | None = None
    campus: Campus


class SupportCard(Model):
    """A person first: shown as card 0 for care-first, or as a gentle block on 'concern'."""
    title: str
    message: str
    options: list[SupportOption]


class Place(Model):
    venue: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    campus: Campus


class SourceRef(Model):
    name: str
    url: str | None = None
    verified_on: date | None = None


class Item(Model):
    id: str
    kind: Literal["event", "resource", "online", "study", "place", "micro"]
    title: str
    summary: str | None = None
    dimensions: list[Dimension] = []
    url: str | None = None
    phone: str | None = None
    hours_text: str | None = None
    synthetic: bool = False


class GoingCount(Model):
    count: int | None = Field(None, description="Only set when 5 or more.")
    label: str = Field(description="'14 Newark students are going', 'A few students are going', or ''.")


class ErrorBody(Model):
    error: str
    message: str
