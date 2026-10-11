"""Fixtures must match the live response models exactly, and every route must answer in fixture mode."""
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.models.common import CrisisResponse
from app.models.demo import PersonasResponse, ResetResponse, SessionResponse, SkipAheadResponse
from app.models.loop import CommitResult, FollowupResponse, InviteAccepted, InviteView, SubscriptionResult
from app.models.social import PulseResponse, SameHere, WinResult
from app.models.staff import DipsResponse, FunnelResponse, GapsResponse, RetakesResponse, WeeklyResponse
from app.models.student import (
    AskResult, CardResponse, DeleteResult, FocusResponse, InboxResponse, MapResponse, MemoryList, NextResponse,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

REGISTRY = {
    "me_map": MapResponse, "me_focus": FocusResponse, "me_focus_crisis": CrisisResponse, "me_next": NextResponse,
    "me_next_after_decline": NextResponse, "me_card": CardResponse, "me_memory": MemoryList, "delete_result": DeleteResult,
    "me_inbox": InboxResponse, "session": SessionResponse, "subscription": SubscriptionResult, "commitment": CommitResult,
    "followup": FollowupResponse, "pulse": PulseResponse, "win_accepted": WinResult, "win_crisis": WinResult,
    "same_here": SameHere, "skip_ahead": SkipAheadResponse, "staff_funnel": FunnelResponse, "staff_gaps": GapsResponse,
    "staff_weekly": WeeklyResponse, "staff_dips": DipsResponse, "staff_retakes": RetakesResponse,
    "personas": PersonasResponse, "ask": AskResult, "reset": ResetResponse, "invite": InviteView, "invite_accepted": InviteAccepted,
}

ALL = sorted(FIXTURES.glob("*/*.json"))


@pytest.mark.parametrize("path", ALL, ids=[f"{p.parent.name}/{p.stem}" for p in ALL])
def test_fixture_validates(path: Path):
    model = REGISTRY.get(path.stem)
    assert model is not None, f"fixture {path} has no registered model"
    TypeAdapter(model).validate_python(json.loads(path.read_text(encoding="utf-8")))


def test_every_fixture_says_synthetic():
    for p in ALL:
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data.get("synthetic") is True, p


STUDENTS = ["andre", "priya", "taylor", "sofia", "jordan"]
STUDENT_GETS = ["/me/map", "/me/next", "/me/card", "/me/memory", "/me/inbox", "/pulse"]
STAFF_GETS = ["/staff/funnel", "/staff/gaps", "/staff/weekly", "/staff/dips", "/staff/retakes"]


@pytest.fixture
def client(fixture_mode_client):
    return fixture_mode_client


def _token(client, persona):
    r = client.post("/demo/session", json={"persona": persona})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.mark.parametrize("persona", STUDENTS)
def test_student_routes_fixture_mode(client, persona):
    h = _token(client, persona)
    for path in STUDENT_GETS:
        r = client.get(path, headers=h)
        assert r.status_code == 200, (path, r.text)
        assert r.headers.get("X-Compass-Fallback") == "fixture"
    r = client.post("/me/focus", headers=h, json={"dimension": "social", "barriers": ["no_time"]})
    assert r.status_code == 200 and r.json()["kind"] == "profile"
    r = client.post("/me/focus", headers=h, json={"dimension": "social", "text": "honestly I want to die"})
    assert r.json()["kind"] == "crisis"
    assert all(line["contact"] for line in r.json()["lines"])
    r = client.post("/commitments", headers=h, json={"rec_id": 1})
    assert r.status_code == 200 and r.json()["kind"] == "commitment"
    r = client.post("/followups/9001", headers=h, json={"went": True, "helped": 4})
    assert r.status_code == 200


def test_staff_routes_fixture_mode(client):
    h = _token(client, "staff")
    for path in STAFF_GETS:
        r = client.get(path, headers=h)
        assert r.status_code == 200, (path, r.text)
        assert r.json()["min_group_size"] == 10


def test_staff_routes_reject_student_tokens(client):
    h = _token(client, "andre")
    assert client.get("/staff/funnel", headers=h).status_code == 403


def test_student_routes_need_token(client):
    assert client.get("/me/map").status_code == 401
    assert client.get("/me/map", headers={"Authorization": "Bearer v1.andre.x.forged"}).status_code == 401


def test_public_invite_has_no_student_fields(client):
    r = client.get("/invites/fixture-invite")
    assert r.status_code == 200
    blob = json.dumps(r.json()).lower()
    for banned in ("student_id", "demo-", "score", "emotional", "persona"):
        assert banned not in blob


def test_focus_text_length_capped(client):
    h = _token(client, "andre")
    r = client.post("/me/focus", headers=h, json={"dimension": "social", "text": "x" * 501})
    assert r.status_code == 422
    assert "xxxx" not in r.text  # never echo free text back
