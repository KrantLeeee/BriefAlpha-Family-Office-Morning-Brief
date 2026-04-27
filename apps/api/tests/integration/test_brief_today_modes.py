"""Task 2.4 + 2.5 integration tests: brief response stamps `system`
envelope and respects mode for cache-miss handling."""
import pytest
from fastapi.testclient import TestClient


def _make_app(monkeypatch, mode: str):
    monkeypatch.setenv("BRIEFALPHA_MODE", mode)
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_REDIS", "1")  # use in-memory cache
    if mode == "live":
        # Force provider=anthropic so the precondition's provider-specific
        # key check matches the ANTHROPIC_API_KEY we set below.
        monkeypatch.setenv("BRIEFALPHA_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        from briefalpha_api.settings import get_settings as _gs
        _gs.cache_clear()
        # avoid resolving against real secrets file on dev box
        import briefalpha_api.config.live_preconditions as lp_mod
        from pathlib import Path
        import tempfile
        td = tempfile.mkdtemp()
        monkeypatch.setattr(lp_mod, "SECRETS_DIR", Path(td))
        # SEC UA is now read from data_sources.yml (not env). Provide a
        # tmp YAML with a real UA so the precondition passes.
        ua_yaml = Path(td) / "data_sources.yml"
        ua_yaml.write_text("sec:\n  user_agent: 'BriefAlpha/dev ci@mycompany.com'\n")
        monkeypatch.setattr(lp_mod, "_DATA_SOURCES_PATH", ua_yaml)

    # IMPORTANT: clear any cached app object from prior tests
    import importlib
    import briefalpha_api.main
    importlib.reload(briefalpha_api.main)
    from briefalpha_api.main import app
    return app


def test_demo_cache_miss_returns_fixture_with_system_stamp(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        resp = client.get("/api/brief/today")
        assert resp.status_code == 200
        body = resp.json()
        assert body["system"]["mode"] == "demo"
        assert body["system"]["status"] == "ready"
        assert body["system"]["data_quality"] == "fixture"
        # fixture content present
        assert body["base_case"]["headline"]
        assert len(body["judgements"]) > 0


def test_live_cache_miss_returns_empty_skeleton(monkeypatch):
    app = _make_app(monkeypatch, "live")
    with TestClient(app) as client:
        resp = client.get("/api/brief/today")
        assert resp.status_code == 200
        body = resp.json()
        assert body["system"]["mode"] == "live"
        assert body["system"]["status"] == "generating"
        assert body["system"]["data_quality"] == "unavailable"
        # NO fixture content
        assert body["base_case"]["headline"] == ""
        assert body["judgements"] == []
        assert body["macro_pulse"] == []
        # shape still valid for the frontend
        assert body["brief_id"]
        assert body["portfolio_snapshot"]["tiles"] == []


def test_demo_response_includes_last_refreshed_timestamp(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        resp = client.get("/api/brief/today")
        last = resp.json()["system"]["last_refreshed_at"]
        assert last is not None
        # ISO8601 with timezone
        assert "+08:00" in last or "+0800" in last


def test_live_skeleton_audit_mode_follows_settings(monkeypatch):
    """Live skeleton's audit_mode should mirror settings.audit_mode (default 'demo'),
    not hardcode 'compliance'."""
    app = _make_app(monkeypatch, "live")
    with TestClient(app) as client:
        body = client.get("/api/brief/today").json()
        # default settings.audit_mode is "demo"
        assert body["audit_mode"] == "demo"


def test_brief_today_defaults_to_live_when_state_missing(monkeypatch):
    """If app.state.mode is missing (atypical), the route should treat it as
    live (never accidentally serve fixture)."""
    monkeypatch.setenv("BRIEFALPHA_MODE", "demo")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_REDIS", "1")
    import importlib
    import briefalpha_api.main
    importlib.reload(briefalpha_api.main)
    from briefalpha_api.main import app
    # Force-remove app.state.mode after lifespan would have set it; route should
    # still serve a sane response.
    with TestClient(app) as client:
        # mid-test wipe: simulate the missing-state scenario
        if hasattr(app.state, "mode"):
            delattr(app.state, "mode")
        body = client.get("/api/brief/today").json()
        # safer side: live skeleton, never fixture
        assert body["base_case"]["headline"] == ""
        assert body["judgements"] == []
        assert body["system"]["mode"] == "live"
        assert body["system"]["status"] == "generating"
