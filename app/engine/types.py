from dataclasses import dataclass, field
from datetime import datetime, time


@dataclass(frozen=True)
class Window:
    weekday: int          # Monday = 0
    start: time
    end: time
    label: str            # "Tue 12:20-14:30"


@dataclass
class KbItem:
    id: str
    kind: str
    title: str
    campus: str
    cost: str = "unknown"
    summary: str | None = None
    summary_es: str | None = None
    venue: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    rung: int | None = None
    solo_friendly: bool | None = None
    url: str | None = None
    phone: str | None = None
    hours_text: str | None = None
    open_hours: dict | None = None
    synthetic: bool = False
    demo_pin: bool = False
    series_key: str | None = None
    formats: frozenset[str] = frozenset()
    dims: dict[str, float] = field(default_factory=dict)
    causes: frozenset[str] = frozenset()
    barriers: frozenset[str] = frozenset()
    audiences: frozenset[str] = frozenset()
    source: str = ""
    attribution: str | None = None
    source_url: str | None = None
    verified_on: object = None
    all_day: bool = False
    arc_activity_id: str | None = None


@dataclass
class StudentCtx:
    id: str
    campus: str
    language: str = "en"
    home_area: str | None = None
    housing: str | None = None
    focus: str | None = None
    barriers: tuple[str, ...] = ()
    windows: tuple[Window, ...] = ()
    target_rung: int = 1
    free_only: bool = True
    declined: frozenset[str] = frozenset()
    committed: frozenset[str] = frozenset()
    care_first: bool = False


@dataclass(frozen=True)
class MemoryFact:
    id: int
    kind: str
    key: str
    statement: str
    confidence: float = 0.6


@dataclass
class HelpedStats:
    """Cohort feedback: key (series_key or item id) -> (helped>=4 count, attended count)."""
    by_key: dict[str, tuple[int, int]] = field(default_factory=dict)
    prior: float = 0.6
    cohort_label: str = "similar students"


@dataclass
class Scored:
    item: KbItem
    score: float
    components: dict[str, float]
    component_text: dict[str, str]
    filters: list[tuple[str, str]]
    memory: list[tuple[MemoryFact, float]]
    walk_min: int | None
    window_label: str | None
    distance_note: str | None
    penalty: float = 0.0
    helped_n: int = 0
    fallback: bool = False


@dataclass
class RankResult:
    care_first: bool
    picks: list[Scored]
    considered: int
    engine_version: str
