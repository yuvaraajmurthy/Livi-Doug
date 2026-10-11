"""The demo cannot fail: Bedrock blocked -> templates and lexicon; DB down -> fixtures."""
import time

import pytest

from app.llm import bedrock
from app.safety.check import check_text


@pytest.fixture
def bedrock_blocked(monkeypatch):
    def boom(*a, **k):
        raise bedrock.ModelUnavailable("blocked")
    monkeypatch.setattr(bedrock, "converse", boom)
    monkeypatch.setattr("app.safety.classifier.converse", boom)
    monkeypatch.setattr("app.safety.barrier_map.converse", boom)
    monkeypatch.setattr("app.safety.moderation.converse", boom)
    monkeypatch.setattr("app.llm.wording.converse", boom)
    yield


def test_crisis_still_caught_with_bedrock_blocked(bedrock_blocked):
    assert check_text("i want to end my life").label == "crisis"


def test_ambiguous_text_fails_safe_to_concern(bedrock_blocked):
    v = check_text("everything has been a lot lately and I don't know")
    assert v.label == "concern" and v.stage == "fallback"


def test_ordinary_short_text_passes_with_bedrock_blocked(bedrock_blocked):
    assert check_text("no time").label == "none"


def test_barrier_mapping_falls_back_to_keywords(bedrock_blocked):
    from app.safety.barrier_map import map_text
    b, c, src = map_text("I work until 10 most nights and money is tight")
    assert src == "keyword" and "money" in b and "works_evenings" in c


def test_moderation_rules_only_when_model_down(bedrock_blocked):
    from app.safety.moderation import moderate
    assert moderate("Went to the farmers market, felt good")[0] == "approve"
    assert moderate("hung out with Jessica")[0] == "hold"


def test_wording_generation_returns_none_quickly(bedrock_blocked):
    from app.llm import wording
    t = time.perf_counter()
    assert wording.generate("why", {"title": "X", "cost": "free"}, "en") is None
    assert time.perf_counter() - t < 0.5


def test_db_down_serves_fixtures(monkeypatch):
    """Point the pool at a dead port: student routes must answer from fixtures with the fallback header."""
    from fastapi.testclient import TestClient

    import app.db as db
    from config.settings import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "mode", "live")
    monkeypatch.setattr(s, "database_url", "postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1")
    monkeypatch.setattr(s, "run_dispatcher", False)
    monkeypatch.setattr(s, "run_wording_worker", False)
    db.close_pool()
    monkeypatch.setattr(db, "_pool", None)
    from app.main import create_app
    with TestClient(create_app()) as c:
        t = c.post("/demo/session", json={"persona": "andre"}).json()["token"]
        for path in ("/me/map", "/me/next", "/pulse"):
            r = c.get(path, headers={"Authorization": f"Bearer {t}"})
            assert r.status_code == 200, (path, r.text)
            assert r.headers.get("X-Compass-Fallback") == "fixture"
    db.close_pool()
