"""Shared pytest fixtures.

Test hermetic guarantees:
  * Secrets-check is skipped (BRIEFALPHA_SKIP_SECRETS_CHECK=1).
  * `BRIEFALPHA_DB_URL` is steered at a per-pytest tmp sqlite file before
    any briefalpha_api modules are imported, so the engine in
    `briefalpha_api.db.session` is created against the test database.
  * `data/.secrets/alias_key` is provisioned in a tmp data dir and the
    settings module's path constants are redirected at it. This lets the
    AES-GCM alias-map storage encrypt without touching the real workspace.
  * No real network — yfinance / GDELT adapters fail-soft inside ingestion.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Skip secrets check during tests.
os.environ.setdefault("BRIEFALPHA_SKIP_SECRETS_CHECK", "1")
# Don't spawn the APScheduler instance in tests — cron jobs would race the
# test database lifecycle and add noise.
os.environ.setdefault("BRIEFALPHA_DISABLE_SCHEDULER", "1")
# Disable redis entirely; routers fall back gracefully (cache miss path).
os.environ.setdefault("BRIEFALPHA_DISABLE_REDIS", "1")

# Make the package importable when pytest runs from apps/api.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Hermetic data dir bootstrap.
#
# This runs at conftest *import* time — i.e. before any test module imports
# briefalpha_api modules. By steering the env vars + monkey-patching the
# settings module constants here, we guarantee that the SessionLocal engine
# (built from get_settings().db_url at first import) binds to a tmp DB
# instead of the real `data/briefalpha.db`.
# ---------------------------------------------------------------------------

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="briefalpha_test_"))
_DATA_DIR = _TMP_ROOT / "data"
_SECRETS_DIR = _DATA_DIR / ".secrets"
_ALIAS_MAPS_DIR = _DATA_DIR / "alias_maps"
_SECRETS_DIR.mkdir(parents=True, exist_ok=True)
_ALIAS_MAPS_DIR.mkdir(parents=True, exist_ok=True)

# AES-GCM alias_key (32 bytes = AES-256).
_ALIAS_KEY_PATH = _SECRETS_DIR / "alias_key"
if not _ALIAS_KEY_PATH.exists():
    _ALIAS_KEY_PATH.write_bytes(os.urandom(32))
    _ALIAS_KEY_PATH.chmod(0o600)

# Stub LLM keys file — providers._api_key sees `replace-me` and serves the
# deterministic stub response.
_LLM_KEYS_PATH = _SECRETS_DIR / "llm_api_keys.json"
if not _LLM_KEYS_PATH.exists():
    _LLM_KEYS_PATH.write_text(
        '{"anthropic":"replace-me","openai":"replace-me"}',
        encoding="utf-8",
    )
    _LLM_KEYS_PATH.chmod(0o600)

# Steer the DB URL before any module reads it.
_DB_PATH = _DATA_DIR / "briefalpha_test.db"
os.environ["BRIEFALPHA_DB_URL"] = f"sqlite+aiosqlite:///{_DB_PATH}"

# Patch the settings module constants. These are referenced at runtime by
# `anonymization.map_storage` and `secrets_check`; rewriting them here means
# the very first usage will land on our tmp dir.
from briefalpha_api import settings as _settings_mod  # noqa: E402

_settings_mod.DATA_DIR = _DATA_DIR
_settings_mod.SECRETS_DIR = _SECRETS_DIR
_settings_mod.ALIAS_MAPS_DIR = _ALIAS_MAPS_DIR
_settings_mod.get_settings.cache_clear()


def _create_schema_if_needed() -> None:
    """Create all tables (including FTS5 virtual) in the tmp sqlite file.

    Called once per test session via a session-scoped autouse fixture below.
    `Base.metadata.create_all` doesn't know about the FTS5 virtual table
    (it's created via raw DDL in the alembic migration), so we issue the
    CREATE VIRTUAL TABLE manually here.
    """
    import asyncio

    from sqlalchemy import text

    from briefalpha_api.db.models import Base
    from briefalpha_api.db.session import engine

    async def _create_all() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
                        evidence_id UNINDEXED,
                        brief_id UNINDEXED,
                        title,
                        excerpt,
                        detected_tickers,
                        chunk_type UNINDEXED,
                        source_tier UNINDEXED,
                        tokenize='unicode61'
                    )
                    """
                )
            )

    asyncio.run(_create_all())


import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_test_db() -> None:
    """Session-scoped autouse to materialize the schema once."""
    _create_schema_if_needed()
    yield
