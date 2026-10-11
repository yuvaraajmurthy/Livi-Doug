"""Fixture responses: the demo's last line of defence.

Files live at fixtures/<persona>/<key>.json. Used when COMPASS mode is 'fixtures', or
automatically when the database is unreachable on a student/demo route.
"""
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from config.settings import ROOT

FIXTURE_DIR = ROOT / "fixtures"


@lru_cache(maxsize=512)
def _load(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def fixture(persona: str, key: str, now: datetime | None = None) -> dict:
    path = FIXTURE_DIR / persona / f"{key}.json"
    if not path.exists():
        path = FIXTURE_DIR / "_shared" / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"no fixture {persona}/{key}")
    data = json.loads(_load(str(path)))
    if now is not None and isinstance(data, dict) and "now" in data:
        data["now"] = now.isoformat()
    return data


def has_fixture(persona: str, key: str) -> bool:
    return (FIXTURE_DIR / persona / f"{key}.json").exists() or (FIXTURE_DIR / "_shared" / f"{key}.json").exists()
