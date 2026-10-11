"""Notification timing rules, lock-screen safety of all copy, grounding check, moderation rules."""
from datetime import datetime

import pytest

from app.clock import NY
from app.llm import grounding, templates
from app.loop import notify
from app.safety.moderation import rules


def dt(m, d, h, mi=0):
    return datetime(2026, m, d, h, mi, tzinfo=NY)


def test_quiet_hours():
    assert notify.in_quiet(dt(10, 13, 23, 0))
    assert notify.in_quiet(dt(10, 13, 7, 59))
    assert not notify.in_quiet(dt(10, 13, 8, 0))
    assert notify.after_quiet(dt(10, 13, 23, 30)) == dt(10, 14, 8, 0)
    assert notify.after_quiet(dt(10, 14, 2, 0)) == dt(10, 14, 8, 0)
    assert notify.after_quiet(dt(10, 14, 12, 0)) == dt(10, 14, 12, 0)


def test_fresh_start_days():
    days = notify.fresh_start_days(dt(10, 12, 9), dt(10, 26, 11))
    assert days == [dt(10, 12, 10), dt(10, 19, 10), dt(10, 26, 10)]
    nov = notify.fresh_start_days(dt(10, 30, 0), dt(11, 3, 0))
    assert dt(11, 1, 10) in nov and dt(11, 2, 10) in nov


@pytest.mark.parametrize("lang", ["en", "es"])
@pytest.mark.parametrize("care", [False, True])
def test_notification_copy_is_lock_screen_safe(lang, care):
    for title in ("Commuter lunch and board games (sample)", "Busch Learning Center", "Livingston halls game night"):
        f = {"title": title, "venue": "Paul Robeson Campus Center"}
        for t, b in (templates.reminder(f, care, lang), templates.followup(f, lang)):
            assert not notify.is_banned(t + " " + b), (t, b)


def test_banned_words_detected():
    assert notify.is_banned("Feeling lonely? Your social score is low")


FACTS = {"title": "Commuter lunch and board games", "window_label": "Fits your Tuesday gap, 12:20–2:30", "walk_min": 3,
         "cost": "free", "venue": "Paul Robeson Campus Center", "barriers_hit": ["no_time"]}


def test_grounding_accepts_faithful_line():
    assert grounding.check("It fits your Tuesday gap, it's a 3-minute walk, and the games mean you don't need small talk.", FACTS) == []


@pytest.mark.parametrize("bad", [
    "Your Tuesday classes don't start until 2pm, so you have time.",
    "It's only $5 and fits your Tuesday gap.",
    "Great for your depression, and it's free.",
    "Join Maria Lopez at the Paul Robeson Campus Center on Friday.",
    "Your social score of 1.9 means you need this.",
])
def test_grounding_rejects_invented_or_unsafe(bad):
    assert grounding.check(bad, FACTS)


def test_grounding_rejects_free_when_cost_unknown():
    assert "claims_free" in grounding.check("It's free and close.", {**FACTS, "cost": "unknown"})


@pytest.mark.parametrize("text,decision", [
    ("Ate lunch on campus instead of in my car. Small thing, felt good.", "approve"),
    ("Went to yoga with Jessica and it was great", "hold"),
    ("text me at 732-555-0101 if you want to come", "hold"),
    ("you should all take melatonin before exams", "hold"),
    ("my roommate is an idiot", "reject"),
    ("follow me @scarletgamer", "hold"),
])
def test_moderation_rules(text, decision):
    assert rules(text)[0] == decision


def test_why_template_never_says_free_for_unknown_cost():
    line = templates.why({**FACTS, "cost": "unknown", "barriers_hit": []}, "en")
    assert "free" not in line.lower()
    assert templates.why({**FACTS, "cost": "free"}, "es")
