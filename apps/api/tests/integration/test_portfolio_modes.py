"""Mode-aware /api/portfolio: demo serves fixture, live reads the real DB."""
import asyncio
import importlib

from fastapi.testclient import TestClient


def _make_app(monkeypatch, mode: str):
    monkeypatch.setenv("BRIEFALPHA_MODE", mode)
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_REDIS", "1")
    if mode == "live":
        monkeypatch.setenv("BRIEFALPHA_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        from briefalpha_api.settings import get_settings as _gs
        _gs.cache_clear()
        import briefalpha_api.config.live_preconditions as lp_mod
        from pathlib import Path
        import tempfile
        td = tempfile.mkdtemp()
        monkeypatch.setattr(lp_mod, "SECRETS_DIR", Path(td))
        ua_yaml = Path(td) / "data_sources.yml"
        ua_yaml.write_text("sec:\n  user_agent: 'BriefAlpha/dev ci@mycompany.com'\n")
        monkeypatch.setattr(lp_mod, "_DATA_SOURCES_PATH", ua_yaml)
    import briefalpha_api.main
    importlib.reload(briefalpha_api.main)
    from briefalpha_api.main import app
    return app


async def _purge_portfolio() -> None:
    from sqlalchemy import delete

    from briefalpha_api.db.models import Portfolio, Watchlist
    from briefalpha_api.db.session import SessionLocal

    async with SessionLocal() as s:
        await s.execute(delete(Portfolio))
        await s.execute(delete(Watchlist))
        await s.commit()


def test_demo_returns_fixture_portfolio_with_is_demo_true(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        resp = client.get(
            "/api/portfolio",
            headers={"Authorization": "Bearer test-admin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_demo"] is True
        # Fixture content present (10 demo tiles, 3 watchlist items).
        assert len(body["tiles"]) >= 1
        assert len(body["watchlist"]) >= 1


def test_live_empty_db_returns_empty_state_no_fixture(monkeypatch):
    asyncio.run(_purge_portfolio())
    app = _make_app(monkeypatch, "live")
    with TestClient(app) as client:
        resp = client.get(
            "/api/portfolio",
            headers={"Authorization": "Bearer test-admin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_demo"] is False
        # Live mode + empty DB -> empty arrays; never fixture content.
        assert body["tiles"] == []
        assert body["watchlist"] == []
        assert body["as_of_hkt"] == ""
