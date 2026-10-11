import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ENV", "test")


@pytest.fixture(autouse=True)
def _never_invoke_send_text_lambda(monkeypatch):
    """The sendText Lambda emails a real person: no test may reach it. Tests that need it patch assist_aws.client."""
    from app.chat import assist_aws
    real = assist_aws.client

    def guarded(service, region):
        if service == "lambda":
            raise AssertionError("tests must not invoke the real sendText Lambda")
        return real(service, region)
    monkeypatch.setattr(assist_aws, "client", guarded)


@pytest.fixture
def fake_aws(monkeypatch):
    """Route app.chat.assist_aws.client(service, region) to fakes: fake_aws("lambda", invoke={...}) -> FakeAWSClient.
    fake_aws.regions records (service, region) for every client made."""
    from app.chat import assist_aws
    from tests.chat.fakes import FakeAWSClient
    fakes: dict = {}
    regions: list = []

    def use(service: str, **responses):
        fakes[service] = FakeAWSClient(**responses)
        return fakes[service]

    def client(service, region):
        regions.append((service, region))
        return fakes[service]
    monkeypatch.setattr(assist_aws, "client", client)
    assist_aws.clear_cache()
    use.regions = regions
    yield use
    assist_aws.clear_cache()


@pytest.fixture
def bedrock_on(monkeypatch):
    """Let the guardrail fetch run (live_db switches Bedrock off). Pair with fake_aws."""
    from config.settings import get_settings
    monkeypatch.setattr(get_settings(), "bedrock_enabled", True)


@pytest.fixture
def fixture_mode_client(monkeypatch):
    from fastapi.testclient import TestClient

    from config.settings import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "mode", "fixtures")
    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c


# --- Live-mode fixtures against the test database (TEST_DATABASE_URL in .env); models are forced off. ---------------
def _test_db_url() -> str | None:
    if os.environ.get("TEST_DATABASE_URL"):
        return os.environ["TEST_DATABASE_URL"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("TEST_DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return None


@pytest.fixture(scope="session")
def live_db():
    url = _test_db_url()
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    os.environ.update({
        "DATABASE_URL": url, "MODE": "live", "FORCE_TEMPLATES": "true", "BEDROCK_ENABLED": "false",
        "RUN_DISPATCHER": "false", "RUN_WORDING_WORKER": "false",
    })
    from config.settings import get_settings
    get_settings.cache_clear()
    from app.db import close_pool, connect_direct
    close_pool()
    from db.migrate import migrate
    from db.seed import seed_all
    with connect_direct() as c:
        migrate(c)
        seed_all(c, kb=True)
        c.commit()
    yield url
    close_pool()


@pytest.fixture
def client(live_db):
    from fastapi.testclient import TestClient

    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def db(live_db):
    from app.db import connect_direct
    with connect_direct() as c:
        c.autocommit = True
        yield c


@pytest.fixture
def staff_headers(client):
    t = client.post("/demo/session", json={"persona": "staff"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}
