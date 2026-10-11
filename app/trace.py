"""Per-request trace for the X-Compass-Trace header: numbers and enum words only, never free text or scores.

The middleware puts a fresh dict in the context var; handlers (threadpool or async) see the same dict object and
add facts with note(). Used by the stage demo to show truthful evidence (which safety stage caught text, how many
items were ranked, whether wording came from AI or a template)."""
import re
from contextvars import ContextVar

_TRACE: ContextVar[dict[str, str] | None] = ContextVar("compass_trace", default=None)
_SAFE = re.compile(r"^[A-Za-z0-9_.\-]{1,24}$")


def begin() -> dict[str, str]:
    d: dict[str, str] = {}
    _TRACE.set(d)
    return d


def note(**kv: object) -> None:
    d = _TRACE.get()
    if d is None:
        return
    for k, v in kv.items():
        if v is None:
            continue
        s = f"{v:.1f}" if isinstance(v, float) else str(v)
        if _SAFE.match(s):  # anything that is not a short token is dropped, so free text can never leak
            d[k] = s


def header(d: dict[str, str]) -> str:
    return ";".join(f"{k}={v}" for k, v in d.items())
