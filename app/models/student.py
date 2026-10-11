from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import Field

from app.models.common import (
    Band, BarrierChip, Campus, Cost, CrisisLine, CrisisResponse, Dimension, Envelope,
    GoingCount, Item, Language, Model, Place, SourceRef, SupportCard,
)


class StudentSummary(Model):
    id: str = Field(description="Pseudonymous id. Never a name, email or NetID.")
    persona: str | None = Field(None, description="Demo persona key, e.g. 'andre'.")
    campus: Campus
    level: Literal["undergrad", "grad"] | None = None
    housing: Literal["resident", "commuter"] | None = None
    language: Language = "en"


class DimensionScore(Model):
    dimension: Dimension
    label: str
    score: float
    band: Band
    blurb: str = Field(description="Plain, kind words. No clinical terms.")
    change: float | None = Field(None, description="Change since the previous take, if any.")


class Take(Model):
    take_no: int
    taken_on: date
    total: float
    scores: dict[Dimension, float]


class RetakeNudge(Model):
    show: bool
    message: str
    url: str = "https://my.rutgers.edu"


class Profile(Model):
    focus: Dimension | None = None
    barriers: list[BarrierChip] = []
    barriers_from_text: list[BarrierChip] = []
    free_windows: list[str] = []
    social_rung: int = 1
    free_only: bool = True
    language: Language = "en"


class MapResponse(Envelope):
    student: StudentSummary
    latest: Take
    dimensions: list[DimensionScore] = Field(description="Strengths first, then the rest.")
    strengths: list[Dimension]
    growth_areas: list[Dimension]
    care_first: bool
    previous_takes: list[Take]
    profile: Profile
    retake_nudge: RetakeNudge | None = None


class FocusRequest(Model):
    dimension: Dimension
    barriers: list[BarrierChip] = []
    text: str | None = Field(None, max_length=500)
    free_only: bool | None = None
    free_windows: list[str] | None = Field(None, description="Optional override, e.g. ['Tue 12:20-14:30'].")


class ProfileResult(Envelope):
    kind: Literal["profile"] = "profile"
    profile: Profile
    support: SupportCard | None = Field(None, description="Present when typed text showed concern: gentle offer of people to talk to.")


FocusResponse = Annotated[Union[ProfileResult, CrisisResponse], Field(discriminator="kind")]


class ReasonLine(Model):
    code: str
    text: str


class Component(Model):
    name: Literal["dimension", "barrier", "window", "rung", "helped_similar"]
    weight: float
    score: float
    contribution: float
    text: str


class MemoryReason(Model):
    memory_id: str
    statement: str
    delta: float


class Reasons(Model):
    filters: list[ReasonLine]
    components: list[Component]
    memory: list[MemoryReason]
    distance: str | None = None
    total: float


class Suggestion(Model):
    rec_id: int
    item: Item
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    when_label: str
    window_label: str | None = None
    where: Place
    walk_min: int | None = None
    cost: Cost
    cost_label: str
    rung: int | None = None
    rung_label: str | None = None
    going: GoingCount
    reasons: Reasons
    why: str
    why_source: Literal["ai", "template"]
    pushed: bool = Field(True, description="False under care-first: available, not pushed.")
    source: SourceRef


class NextResponse(Envelope):
    set_id: str
    care_first: bool
    support_card: SupportCard | None = None
    pick: Suggestion
    alternates: list[Suggestion]
    crisis_lines: list[CrisisLine]


class DeclineRequest(Model):
    reason: Literal["swap", "not_now"] = "swap"


class CardResponse(Envelope):
    kind: Literal["step", "support"]
    title: str
    when_label: str | None = None
    line: str
    deep_link: str


class MemorySource(Model):
    type: Literal["you_chose", "rating", "attendance", "decline", "your_words", "rule"]
    label: str
    at: datetime | None = None


class MemoryItem(Model):
    id: str
    kind: str
    statement: str
    source: MemorySource
    used_for: str
    learned_at: datetime | None = None
    last_used_at: datetime | None = None
    deletable: bool = True


class MemoryList(Envelope):
    items: list[MemoryItem]
    note: str = "This is everything Compass keeps about you. Your inventory scores stay in MyRutgers and are only read, never changed."


class DeleteResult(Envelope):
    deleted: int


class InboxItem(Model):
    id: int
    kind: str
    title: str
    body: str
    deep_link: str
    at: datetime
    delivered: Literal["push", "in_app"]


class InboxResponse(Envelope):
    items: list[InboxItem]


class BarrierOption(Model):
    id: BarrierChip
    label: str
    label_es: str


class BarrierMeta(Model):
    barriers: list[BarrierOption]
    dimensions: dict[Dimension, str]
