"""Centralized application settings.

Read from environment variables (prefixed `BRIEFALPHA_`) and
`packages/config/data_sources.yml` at runtime.

Anything in this module is safe to log; it MUST NOT contain secrets.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Matches `sqlite:///./xxx` and `sqlite+aiosqlite:///./xxx` (3 slashes + ./).
# Four-slash absolute forms (sqlite:////abs) and `:memory:` are NOT matched —
# they're already cwd-independent.
_SQLITE_REL_PATH = re.compile(r"^(sqlite(?:\+[\w]+)?:///)\.\/(.+)$")

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
SECRETS_DIR = DATA_DIR / ".secrets"
ALIAS_MAPS_DIR = DATA_DIR / "alias_maps"
SYMBOL_MAPS_DIR = DATA_DIR / "symbol_maps"
RESEARCH_PDFS_DIR = REPO_ROOT / "research_pdfs"
CONFIG_DIR = REPO_ROOT / "packages" / "config"
PROMPTS_DIR = REPO_ROOT / "packages" / "prompts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BRIEFALPHA_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    brief_timezone: str = "Asia/Hong_Kong"
    brief_delivery_time: str = "08:30"
    audit_mode: str = Field(default="demo", pattern="^(demo|compliance)$")
    llm_provider: str = Field(default="anthropic", pattern="^(anthropic|openai)$")

    redis_url: str = "redis://localhost:6379/0"
    db_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'briefalpha.db'}"

    @field_validator("db_url")
    @classmethod
    def _anchor_relative_sqlite_to_repo_root(cls, v: str) -> str:
        """`.env`/`.env.example` ship `sqlite+aiosqlite:///./data/briefalpha.db`,
        which SQLite resolves against the process cwd. The API can be started
        from either `apps/api` (uvicorn invocation) or the repo root (`make`
        targets), and that ambiguity caused source-health to crash with
        "unable to open database file" when launched from `apps/api`. Anchor
        the leading `./` to REPO_ROOT so the URL is cwd-independent."""
        m = _SQLITE_REL_PATH.match(v)
        if not m:
            return v
        scheme, rel = m.group(1), m.group(2)
        return f"{scheme}{(REPO_ROOT / rel).resolve()}"

    # Feature switches
    coarse_bucket_mode_threshold: int = 15
    k_anonymity_threshold: int = 3
    research_upload_limit: int = 5
    auto_expand_universe: bool = False
    third_party_embedding_enabled: bool = False
    degradation_threshold: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
