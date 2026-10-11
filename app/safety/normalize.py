"""Text variants for lexicon matching. Matching runs on every variant; any hit counts."""
import re
import unicodedata

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
_APOS = re.compile(r"[’'`´]")
_SPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s💊🔫🪦⚰️]", re.UNICODE)


def _strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def _base(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = _APOS.sub(" ", t)          # "don't" -> "don t", "can't" -> "can t"
    t = _strip_accents(t)
    t = _PUNCT.sub(" ", t)
    return _SPACE.sub(" ", t).strip()


def variants(text: str) -> list[str]:
    b = _base(text)
    out = [b,
           re.sub(r"(.)\1{2,}", r"\1", b),        # "dieeee" -> "die"
           re.sub(r"(.)\1{2,}", r"\1\1", b),      # "killll" -> "kill"
           b.translate(_LEET),                     # "k1ll mys3lf" -> "kill myself"
           b.replace(" t ", "t ")]                 # "don t" -> "dont"
    seen, uniq = set(), []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq
