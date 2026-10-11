"""Event card detail (spec 2026-10-11 §3.7) and chat API bodies."""
from datetime import datetime

from pydantic import Field

from app.models.common import GoingCount, Model, SourceRef


class ItemDetail(Model):
    id: str
    kind: str
    title: str
    summary: str | None
    dimensions: list[str]
    synthetic: bool
    starts_at: datetime | None
    ends_at: datetime | None
    when_label: str
    venue: str | None
    address: str | None
    lat: float | None
    lon: float | None
    campus: str
    cost: str
    cost_label: str
    url: str | None
    phone: str | None
    hours_text: str | None
    walk_min: int | None
    going: GoingCount
    source: SourceRef
    directions_url: str = Field(description="Google Maps directions (coordinates) or search (venue/address) link.")
    calendar_url: str | None = Field(None, description="Google Calendar template link for timed events.")
    ics_url: str | None = None


class ChatRequest(Model):
    message: str = Field(min_length=1, max_length=500)
    conversation_id: str | None = None


class ChatNew(Model):
    conversation_id: str
