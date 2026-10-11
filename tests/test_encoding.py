"""Guard against double-encoded (mojibake) text in anything we ship to the UI."""
import json
from pathlib import Path

BAD = ("Ã", "â€", "Â")
ROOT = Path(__file__).resolve().parents[1]


def _files():
    yield from (ROOT / "fixtures").rglob("*.json")
    yield from (ROOT / "config").glob("*.yaml")
    yield from (ROOT / "seed").rglob("*.yaml")


def test_no_mojibake_in_fixtures_or_config():
    offenders = []
    for f in _files():
        text = f.read_text(encoding="utf-8")
        if f.suffix == ".json":
            text = json.dumps(json.loads(text), ensure_ascii=False)
        if any(b in text for b in BAD):
            offenders.append(str(f.relative_to(ROOT)).replace("\\", "/"))
    assert offenders == []
