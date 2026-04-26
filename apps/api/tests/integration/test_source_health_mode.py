"""Task 7.1: /api/source-health is mode-aware."""
import asyncio
import importlib

import pytest
from fastapi.testclient import TestClient


def _make_app(monkeypatch, mode: str):
    monkeypatch.setenv("BRIEFALPHA_MODE", mode)
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_REDIS", "1")
    if mode == "live":
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
        import briefalpha_api.config.live_preconditions as lp_mod
        from pathlib import Path
        import tempfile
        td = tempfile.mkdtemp()
        monkeypatch.setattr(lp_mod, "SECRETS_DIR", Path(td))
    import briefalpha_api.main
    importlib.reload(briefalpha_api.main)
    from briefalpha_api.main import app
    return app


async def _purge_source_health_history() -> None:
    from sqlalchemy import delete

    from briefalpha_api.db.models import SourceHealthHistory
    from briefalpha_api.db.session import SessionLocal

    async with SessionLocal() as s:
        await s.execute(delete(SourceHealthHistory))
        await s.commit()


@pytest.fixture
def _wipe_source_health():
    """Truncate source_health_history before and after the test so prior
    integration tests that populated the table don't leak into the
    'empty DB' assertion."""
    asyncio.run(_purge_source_health_history())
    yield
    asyncio.run(_purge_source_health_history())


def test_demo_returns_fixture_with_is_demo_true(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        body = client.get("/api/source-health").json()
        assert all(row["is_demo"] is True for row in body["rows"])


def test_live_no_db_returns_empty_rows_with_failed_overall(
    monkeypatch, _wipe_source_health
):
    app = _make_app(monkeypatch, "live")
    with TestClient(app) as client:
        body = client.get("/api/source-health").json()
        # live mode + empty DB -> failed overall + empty rows; never fixture content
        assert body["overall"] == "failed"
        assert body["rows"] == []
