"""Mode-aware drawer endpoint: cold cache must NOT leak fixture in live mode."""
import importlib

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


def test_demo_cache_miss_serves_fixture_drawer(monkeypatch):
    """Demo mode: cold cache falls back to fixture (acceptable — demo IS fixture)."""
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        body = client.get("/api/judgement/j1/drawer").json()
        # Fixture's j1 has the recognizable Chinese headline about NVDA Q1.
        assert body["judgement"]["id"] == "j1"
        assert body["judgement"]["title"]  # non-empty
        assert body["judgement"]["evidence"]  # has evidence cards


def test_live_cache_miss_returns_empty_skeleton_no_fixture(monkeypatch):
    """Live mode: cold cache returns an empty skeleton — NEVER fixture content."""
    app = _make_app(monkeypatch, "live")
    with TestClient(app) as client:
        resp = client.get("/api/judgement/j1/drawer")
        assert resp.status_code == 200
        body = resp.json()
        # Skeleton has the requested id but blank/empty content.
        assert body["judgement"]["id"] == "j1"
        assert body["judgement"]["title"] == ""
        assert body["judgement"]["evidence"] == []
        assert body["judgement"]["supplementary_sources"] == []
        assert body["judgement"]["reasoning_chain"] == {}
