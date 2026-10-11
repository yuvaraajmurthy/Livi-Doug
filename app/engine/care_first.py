"""Care-first rule: plain code, config-driven placeholder thresholds. Never a model, never a diagnosis."""
from functools import lru_cache

import yaml

from config.settings import CONFIG_DIR


@lru_cache
def scoring() -> dict:
    return yaml.safe_load((CONFIG_DIR / "scoring.yaml").read_text(encoding="utf-8"))


def band(score: float) -> str:
    s = scoring()["bands"]
    if score < s["low_below"]:
        return "low"
    if score >= s["high_from"]:
        return "high"
    return "middle"


def applies(scores: dict[str, float]) -> bool:
    c = scoring()["care_first"]
    emo = scores.get("emotional")
    if emo is None:
        return False
    if emo <= c["emotional_at_or_below"]:
        return True
    low = scoring()["bands"]["low_below"]
    others_low = sum(1 for d, v in scores.items() if d != "emotional" and v < low)
    return emo < low and others_low >= c["other_low_dimensions"]
