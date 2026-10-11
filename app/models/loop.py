from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import Field

from app.models.common import CrisisResponse, Dimension, Envelope, GoingCount, Item, Model, Place
from app.models.student import MemoryItem


class CommitRequest(Model):
    rec_id: int
    plan_text: str | None = Field(None, max_length=280, description="Student-edited plan. Crisis-checked.")


class CommitResponse(Envelope):
    kind: Literal["commitment"] = "commitment"
    commitment_id: int
    status: Literal["planned", "went", "missed", "cancelled"]
    item: Item
    when_label: str
    where: Place
    plan_text: str
    plan_source: Literal["ai", "template", "student"]
    ics_url: str
    google_calendar_url: str
    reminder_at: datetime | None
    followup_at: datetime | None
    invite_url: str
    invite_token: str
    share_text: str


CommitResult = Annotated[Union[CommitResponse, CrisisResponse], Field(discriminator="kind")]


class InviteView(Envelope):
    token: str
    item: Item
    when_label: str
    where: Place
    going: GoingCount
    accepted: bool
    note: str = "Your friend thought you might like this. No account needed."


class InviteAccepted(Envelope):
    token: str
    accepted: bool
    ics_url: str
    message: str


class FollowupRequest(Model):
    went: bool
    helped: int | None = Field(None, ge=1, le=5)


class ArcStatus(Model):
    status: Literal["mock", "sent", "none"]
    message: str


class ChallengeProgress(Model):
    challenge_id: str
    title: str
    added: int
    progress: int
    goal: int
    pct: float


class NextRung(Model):
    rung: int
    label: str
    message: str


class ProgressDelta(Model):
    dimension: Dimension
    steps_this_month: int
    message: str


class FollowupResponse(Envelope):
    commitment_id: int
    status: Literal["went", "missed"]
    progress: ProgressDelta | None
    arc: ArcStatus
    challenge: ChallengeProgress | None
    next_rung: NextRung | None
    learned: list[MemoryItem]
    win_prompt: bool


class FiredNotification(Model):
    id: int
    kind: Literal["reminder", "followup", "weekly_pick", "retake_nudge", "challenge"]
    title: str
    body: str
    deep_link: str
    send_at: datetime
    delivered: Literal["push", "in_app", "held_budget", "skipped"]
    commitment_id: int | None = None


class VapidKey(Model):
    public_key: str | None = Field(description="VAPID application server key (base64url). Null if push is not configured.")


class PushKeys(Model):
    p256dh: str
    auth: str


class SubscriptionRequest(Model):
    endpoint: str = Field(max_length=2048)
    keys: PushKeys


class SubscriptionResult(Envelope):
    ok: bool
    test_sent: bool = False
