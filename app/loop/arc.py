"""The Arc adapter. Only "this student attended activity X" may ever leave Compass. Never scores.

The Arc (Suitable) has no public API we could find, so MockArc records the credit locally. A real adapter
implements the same one method."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ArcResult:
    status: str        # mock | sent | failed
    message: str


class ArcAdapter(Protocol):
    def record_attendance(self, pseudonym: str, activity_id: str | None, occurred_at: datetime) -> ArcResult: ...


class MockArc:
    """Records nothing outside Compass. The arguments are the complete outbound payload, by design."""
    sent: list[tuple[str, str | None, datetime]] = []

    def record_attendance(self, pseudonym: str, activity_id: str | None, occurred_at: datetime) -> ArcResult:
        MockArc.sent.append((pseudonym, activity_id, occurred_at))
        return ArcResult("mock", "Wellness credit added to The Arc (demo)")


def adapter() -> ArcAdapter:
    return MockArc()
