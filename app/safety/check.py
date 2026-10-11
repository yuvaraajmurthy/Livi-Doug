"""The one entry point for free text. Order: lexicon -> classifier -> fail-safe. Text is never stored or logged."""
import logging
from dataclasses import dataclass
from typing import Literal

from app.safety import classifier
from app.safety.lexicon import scan

log = logging.getLogger("compass.safety")

from concurrent.futures import ThreadPoolExecutor  # noqa: E402

POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="safety")

Source = Literal["barrier_text", "wins_post", "ask_box", "voice", "plan_text"]


@dataclass(frozen=True)
class SafetyVerdict:
    label: Literal["crisis", "concern", "none"]
    stage: Literal["lexicon", "classifier", "fallback", "empty"]
    codes: tuple[str, ...] = ()


def _trivial(text: str) -> bool:
    t = text.strip()
    return len(t) < 12 or len(t.split()) < 3


def check_text(text: str | None, use_classifier: bool = True) -> SafetyVerdict:
    if not text or not text.strip():
        return SafetyVerdict("none", "empty")
    hit = scan(text)
    if hit.label == "crisis":
        return SafetyVerdict("crisis", "lexicon", hit.codes)
    if not use_classifier:
        return SafetyVerdict(hit.label, "lexicon", hit.codes)
    label, who = classifier.classify(text)
    if label is None:
        # Fail safe: if nobody could label it, ambiguous text is treated as concern, never as fine.
        fallback = hit.label if hit.label != "none" else ("none" if _trivial(text) else "concern")
        return SafetyVerdict(fallback, "fallback", hit.codes)
    final = max((hit.label, label), key=classifier.SEVERITY.__getitem__)
    return SafetyVerdict(final, "classifier" if final == label else "lexicon", hit.codes + tuple(f"model:{w}" for w in who))


def record_event(conn, student_id: str | None, source: Source, verdict: SafetyVerdict, action: str) -> None:
    """Logs that the check fired. Never the text."""
    if verdict.label == "none":
        return
    conn.execute(
        "INSERT INTO safety_events (student_id, source, level, action, stage) VALUES (%s, %s, %s, %s, %s)",
        (student_id, source, verdict.label, action, verdict.stage),
    )
    log.info("safety event", extra={"outcome": verdict.label, "route_key": source})
