"""Pure engine tests: no database, no models, no clock reads."""
from dataclasses import replace
from datetime import datetime, timedelta

from app.clock import NY
from app.engine import care_first
from app.engine.rank import parse_window, rank, window_fit
from app.engine.types import HelpedStats, KbItem, MemoryFact, StudentCtx

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=NY)


def dt(m, d, h, mi=0):
    return datetime(2026, m, d, h, mi, tzinfo=NY)


def item(**kw) -> KbItem:
    base = dict(id="x", kind="event", title="X", campus="newark", cost="free", lat=40.7415, lon=-74.1752, rung=2,
                solo_friendly=True, dims={"social": 1.0}, causes=frozenset({"loneliness"}), series_key=None)
    base.update(kw)
    if base["series_key"] is None:
        base["series_key"] = base["id"]
    return KbItem(**base)


ANDRE = StudentCtx(id="DEMO-ANDRE", campus="newark", focus="social", barriers=("no_time", "dont_know_anyone"),
                   windows=(parse_window("Tue 12:20-14:30"), parse_window("Thu 12:20-14:30")), target_rung=2)

LUNCH = item(id="lunch", title="Commuter lunch and board games (sample)", venue="Paul Robeson Campus Center",
             starts_at=dt(10, 13, 12, 30), ends_at=dt(10, 13, 13, 30), formats=frozenset({"games", "food"}))
MIXER = item(id="mixer", title="Club fair mixer", venue="Bradley Hall", rung=3, starts_at=dt(10, 13, 12, 30), ends_at=dt(10, 13, 13, 30),
             lat=40.7409, lon=-74.1739)
EVENING = item(id="evening", title="Evening social", venue="Golden Dome", starts_at=dt(10, 14, 18, 0), ends_at=dt(10, 14, 19, 0))
FAR = item(id="far", title="Far lunch", venue="Elsewhere", lat=40.80, lon=-74.25, starts_at=dt(10, 15, 12, 30), ends_at=dt(10, 15, 13, 30))
PANTRY = item(id="pantry", kind="resource", title="Pantry", dims={"financial": 1.0}, causes=frozenset({"money"}), rung=1)
MICRO = item(id="micro-social-1", kind="micro", title="Text one classmate", campus="online", dims={"social": 1.0})
STATS = HelpedStats(by_key={"lunch": (26, 36)}, prior=0.6, cohort_label="Newark commuters")
ITEMS = [LUNCH, MIXER, EVENING, FAR, PANTRY, MICRO]


def test_andre_gets_the_lunch_in_his_tuesday_gap():
    r = rank(ANDRE, ITEMS, STATS, [], NOW)
    assert r.picks[0].item.id == "lunch"
    assert r.picks[0].window_label.startswith("Fits your Tuesday gap")
    assert r.picks[0].components["dimension"] == 1.0
    assert r.picks[0].helped_n == 36


def test_evening_event_outside_windows_is_filtered():
    r = rank(ANDRE, ITEMS, STATS, [], NOW)
    assert "evening" not in [p.item.id for p in r.picks]


def test_determinism():
    first = [p.item.id for p in rank(ANDRE, ITEMS, STATS, [], NOW).picks]
    for _ in range(20):
        assert [p.item.id for p in rank(ANDRE, ITEMS, STATS, [], NOW).picks] == first


def test_next_rung_prefers_open_social():
    r = rank(replace(ANDRE, target_rung=3), [MIXER, replace(LUNCH, id="lunch2", series_key="lunch2")], HelpedStats(), [], NOW)
    assert r.picks[0].item.id == "mixer"


def test_distance_is_a_tie_breaker_and_penalty():
    near = replace(LUNCH, id="near", series_key="near", starts_at=dt(10, 15, 12, 30), ends_at=dt(10, 15, 13, 30))
    r = rank(ANDRE, [FAR, near], HelpedStats(), [], NOW)
    assert r.picks[0].item.id == "near"
    assert "far" not in [p.item.id for p in r.picks]  # a 2-hour walk cannot fit a 2-hour gap
    no_windows = replace(ANDRE, windows=())
    r2 = rank(no_windows, [FAR, near], HelpedStats(), [], NOW)
    assert [p.item.id for p in r2.picks][:2] == ["near", "far"]
    far = next(p for p in r2.picks if p.item.id == "far")
    assert far.walk_min > 15 and far.penalty > 0


def test_never_empty_when_everything_is_declined():
    ctx = replace(ANDRE, declined=frozenset({"lunch", "mixer", "evening", "far", "pantry"}))
    r = rank(ctx, ITEMS, STATS, [], NOW)
    assert r.picks and r.picks[0].item.kind == "micro"


def test_past_and_beyond_horizon_filtered():
    past = replace(LUNCH, id="past", starts_at=dt(10, 12, 8, 0), ends_at=dt(10, 12, 8, 30))
    late = replace(LUNCH, id="late", starts_at=NOW + timedelta(days=11), ends_at=NOW + timedelta(days=11, hours=1))
    ids = [p.item.id for p in rank(ANDRE, [past, late, LUNCH], STATS, [], NOW).picks]
    assert "past" not in ids and "late" not in ids


def test_paid_filtered_when_free_only():
    paid = replace(LUNCH, id="paid", cost="paid")
    assert "paid" not in [p.item.id for p in rank(ANDRE, [paid, LUNCH], STATS, [], NOW).picks]


def test_window_fit_across_dst():
    # DST ends 2026-11-01; a Tuesday 12:30 event after that is still inside the Tue 12:20-14:30 wall-clock window.
    ev = replace(LUNCH, starts_at=datetime(2026, 11, 3, 12, 30, tzinfo=NY), ends_at=datetime(2026, 11, 3, 13, 30, tzinfo=NY))
    score, label, ok = window_fit(ANDRE, ev, datetime(2026, 11, 2, 9, 0, tzinfo=NY), 3)
    assert ok and score >= 0.9 and "Tuesday" in label


def test_memory_reason_cited_and_removed():
    fact = MemoryFact(id=7, kind="likes_format", key="games", statement="You enjoyed game-based events", confidence=0.8)
    with_mem = rank(ANDRE, ITEMS, STATS, [fact], NOW).picks[0]
    assert [f.id for f, _ in with_mem.memory] == [7]
    assert 0 < with_mem.memory[0][1] <= 0.05
    without = rank(ANDRE, ITEMS, STATS, [], NOW).picks[0]
    assert without.memory == []


def test_root_cause_counts_for_priya():
    blc = item(id="blc", kind="resource", title="Busch Learning Center", campus="new_brunswick", dims={"intellectual": 0.9},
               causes=frozenset({"academic_workload"}), rung=1, lat=40.5227, lon=-74.4652)
    priya = StudentCtx(id="DEMO-PRIYA", campus="new_brunswick", home_area="Busch", focus="physical", barriers=("coursework",))
    r = rank(priya, [blc], HelpedStats(), [], NOW)
    assert r.picks[0].item.id == "blc" and r.picks[0].components["dimension"] == 0.7
    assert r.picks[0].component_text["dimension"].startswith("root_cause")


def test_alternates_are_diverse():
    clones = [replace(LUNCH, id=f"c{i}", series_key="same-series") for i in range(4)]
    r = rank(ANDRE, clones + [MIXER, PANTRY], STATS, [], NOW)
    series = [p.item.series_key for p in r.picks]
    assert len(set(series)) == len(series)


def test_care_first_rule():
    taylor = {"emotional": 1.3, "environmental": 2.5, "financial": 2.4, "intellectual": 2.2, "occupational": 2.4, "physical": 1.9, "social": 1.6, "spiritual": 2.3}
    andre = {"emotional": 2.6, "environmental": 2.9, "financial": 2.1, "intellectual": 3.2, "occupational": 3.0, "physical": 2.7, "social": 1.9, "spiritual": 3.4}
    assert care_first.applies(taylor)
    assert not care_first.applies(andre)
    combo = dict(andre, emotional=2.2, physical=2.0, social=1.9, financial=2.1)
    assert care_first.applies(combo)
    assert not care_first.applies(dict(andre, emotional=2.2))
