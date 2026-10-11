from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.common import Campus, Envelope, Model
from app.models.loop import FiredNotification

Persona = Literal["andre", "priya", "taylor", "sofia", "jordan", "staff"]


class SessionRequest(Model):
    persona: Persona
    now: datetime | None = Field(None, description="Optional simulated start time; defaults to the demo start.")


class SessionResponse(Envelope):
    token: str
    persona: Persona
    role: Literal["student", "staff"]
    student_id: str | None


class PersonaInfo(Model):
    key: Persona
    name: str
    campus: Campus | None
    role_in_demo: str
    synthetic: bool = True


class PersonasResponse(Envelope):
    personas: list[PersonaInfo]


class ClockRequest(Model):
    now: datetime


class SkipAheadRequest(Model):
    to: str = Field("next_due", description="'next_due', a relative step like '+2d' or '+3h', or an ISO datetime.")


class SkipAheadResponse(Envelope):
    previous_now: datetime
    fired: list[FiredNotification]


class ResetResponse(Envelope):
    ok: bool
    seconds: float


class ForceTemplatesRequest(Model):
    on: bool


class HealthCheck(Model):
    ok: bool
    latency_ms: float | None = None
    detail: str | None = None


class Health(Model):
    status: Literal["ok", "degraded", "down"]
    mode: Literal["live", "fixtures"]
    version: str
    checks: dict[str, HealthCheck]
