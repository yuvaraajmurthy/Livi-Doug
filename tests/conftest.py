import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ENV", "test")


@pytest.fixture
def fixture_mode_client(monkeypatch):
    from fastapi.testclient import TestClient

    from config.settings import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "mode", "fixtures")
    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c
