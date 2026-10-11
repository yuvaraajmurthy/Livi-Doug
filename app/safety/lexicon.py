"""Stage 1: deterministic phrase matching. Runs before anything else touches free text."""
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import yaml

from app.safety.normalize import variants
from config.settings import CONFIG_DIR

Label = Literal["crisis", "concern", "none"]


@dataclass(frozen=True)
class LexiconHit:
    label: Label
    codes: tuple[str, ...]


@lru_cache
def _compiled() -> dict[str, list[re.Pattern]]:
    raw = yaml.safe_load((CONFIG_DIR / "safety_lexicon.yaml").read_text(encoding="utf-8"))
    return {k: [re.compile(p, re.UNICODE) for p in raw.get(k, [])] for k in ("crisis", "concern", "idioms")}


def _spans(patterns: list[re.Pattern], texts: list[str]) -> list[tuple[int, int, int, int]]:
    """(variant index, pattern index, start, end) for every match."""
    out = []
    for vi, t in enumerate(texts):
        for pi, p in enumerate(patterns):
            for m in p.finditer(t):
                out.append((vi, pi, m.start(), m.end()))
    return out


def scan(text: str) -> LexiconHit:
    if not text or not text.strip():
        return LexiconHit("none", ())
    pats = _compiled()
    vs = variants(text)
    crisis = _spans(pats["crisis"], vs)
    if crisis:
        return LexiconHit("crisis", tuple(sorted({f"crisis:{pi}" for _, pi, _, _ in crisis})))
    concern = _spans(pats["concern"], vs)
    if not concern:
        return LexiconHit("none", ())
    idioms = _spans(pats["idioms"], vs)
    remaining = [c for c in concern
                 if not any(i[0] == c[0] and i[2] <= c[2] and c[3] <= i[3] for i in idioms)]
    if remaining:
        return LexiconHit("concern", tuple(sorted({f"concern:{pi}" for _, pi, _, _ in remaining})))
    return LexiconHit("none", ("idiom",))


def quick_crisis(text: str) -> bool:
    return scan(text).label == "crisis"
