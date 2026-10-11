from pathlib import Path

import pytest
import yaml

from app.safety.lexicon import scan

P = yaml.safe_load((Path(__file__).parent / "phrases.yaml").read_text(encoding="utf-8"))


def test_set_is_big_enough():
    assert len(P["crisis"]) + len(P["concern"]) >= 60
    assert len(P["false_alarms"]) >= 25


@pytest.mark.parametrize("text", P["crisis"])
def test_crisis_caught_by_stage1(text):
    assert scan(text).label == "crisis", text


@pytest.mark.parametrize("text", P["concern"])
def test_concern_at_least_concern(text):
    assert scan(text).label in ("concern", "crisis"), text


@pytest.mark.parametrize("text", P["false_alarms"])
def test_false_alarms_pass(text):
    assert scan(text).label == "none", text


def test_empty_is_none():
    assert scan("").label == "none"
    assert scan("   ").label == "none"


def test_long_text_still_scanned():
    assert scan("ok " * 400 + "I want to kill myself").label == "crisis"
