"""Runtime settings. Everything tunable lives here or in the YAML files beside it."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://postgres:dev@localhost:5432/compass"
    staff_database_url: str | None = None  # connects as compass_staff_ro; defaults to database_url with SET ROLE
    mode: Literal["live", "fixtures"] = "live"
    env: Literal["dev", "prod", "test"] = "dev"
    version: str = "1.0.0"

    cors_origins: str = "*"
    demo_signing_key: str = "dev-only-change-me"
    public_base_url: str = "http://localhost:8000"

    # Simulated clock default: Monday 2026-10-12 09:00 ET, a fresh start.
    default_now: str = "2026-10-12T09:00:00-04:00"
    timezone: str = "America/New_York"

    aws_region: str = "us-west-2"
    model_wording: str = "us.xai.grok-4.7"
    model_wording_fallback: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    model_fast: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    model_safeguard: str = "openai.gpt-oss-safeguard-20b"
    model_tagging: str = "us.xai.grok-4.7"
    model_embed: str = "us.cohere.embed-v4:0"
    guardrail_id: str | None = None
    guardrail_version: str = "DRAFT"
    inline_timeout_s: float = 1.2
    wording_timeout_s: float = 25.0
    force_templates: bool = False
    bedrock_enabled: bool = True

    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "mailto:compass-demo@example.org"

    dispatcher_interval_s: float = 30.0
    run_dispatcher: bool = True
    run_wording_worker: bool = True

    # On AWS the RDS-managed secret is injected as separate fields; compose them into database_url.
    db_host: str | None = None
    db_port: int = 5432
    db_user: str | None = None
    db_password: str | None = None
    db_name: str = "compass"

    @model_validator(mode="after")
    def _compose_db_url(self):
        if self.db_host and self.db_user and self.db_password:
            from urllib.parse import quote
            self.database_url = (
                f"postgresql://{quote(self.db_user)}:{quote(self.db_password, safe='')}@{self.db_host}:{self.db_port}/{self.db_name}?sslmode=require"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
