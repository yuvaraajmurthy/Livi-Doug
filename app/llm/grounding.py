"""Grounding check: generated wording may only restate facts the engine chose.

Rejects any time, number, price, weekday, month or capitalised place name that is not in the facts,
plus clinical, score, mood and crisis words. Cheap, deterministic, explainable.
"""
import re

BANNED = {
    # clinical / diagnostic
    "depression", "depressed", "anxiety disorder", "disorder", "diagnos", "symptom", "therapy will", "treatment", "patient",
    "mental illness", "medication", "medicine", "prescri", "clinical", "ptsd", "adhd", "bipolar", "insomnia",
    # scores and moods (lock-screen and tone safety)
    "score", "1.9", "low social", "lonely", "loneliness", "struggling", "sad", "isolated",
    # crisis
    "suicide", "self-harm", "crisis", "die", "kill",
    # over-promising
    "guarantee", "will fix", "cure",
}
BANNED_ES = {"depresión", "deprimid", "ansiedad", "trastorno", "diagnóst", "síntoma", "medicamento", "puntaje", "solo y triste", "suicid", "crisis"}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
            "lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado", "domingo"]
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
          "december", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
_NUM = re.compile(r"(?<![\d:])\d+(?::\d{2})?")
_PRICE = re.compile(r"\$\s?\d+")
_TIMEWORD = re.compile(r"\b(\d{1,2})\s?(am|pm|a\.m\.|p\.m\.)\b", re.I)


def _facts_text(facts: dict) -> str:
    parts = []
    for v in facts.values():
        if isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v)
        elif v is not None:
            parts.append(str(v))
    return " ".join(parts).lower()


def check(text: str, facts: dict, lang: str = "en", max_words: int = 40) -> list[str]:
    t = (text or "").strip()
    low = t.lower()
    ft = _facts_text(facts)
    issues = []
    if not t:
        return ["empty"]
    if len(t.split()) > max_words:
        issues.append("too_long")
    for b in (BANNED | BANNED_ES):
        if re.search(r"(?<![\w])" + re.escape(b), low) and b not in ft:
            issues.append(f"banned:{b}")
    fact_numbers = set(_NUM.findall(ft))
    for n in _NUM.findall(low):
        if n not in fact_numbers:
            issues.append(f"number:{n}")
    for p in _PRICE.findall(low):
        issues.append(f"price:{p}")
    for w in WEEKDAYS + MONTHS:
        if re.search(rf"\b{w}\b", low) and w not in ft:
            issues.append(f"date_word:{w}")
    if "free" in low.split() and str(facts.get("cost", "")).lower() != "free":
        issues.append("claims_free")
    if ("gratis" in low) and str(facts.get("cost", "")).lower() != "free":
        issues.append("claims_free")
    # Capitalised multi-word names (places/people) must come from the facts.
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", t):
        name = m.group(1).lower()
        if name not in ft and not any(w in ft for w in name.split() if len(w) > 3):
            issues.append(f"name:{m.group(1)}")
    if "<" in t or "http" in low:
        issues.append("markup")
    return issues
