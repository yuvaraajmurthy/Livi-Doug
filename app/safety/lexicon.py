"""Placeholder until Task 4 lands the full lexicon."""
_CRISIS = ("kill myself", "suicide", "want to die", "end my life", "quiero morir", "kms")


def quick_crisis(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in _CRISIS)
