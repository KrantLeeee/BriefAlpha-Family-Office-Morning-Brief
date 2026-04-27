"""Tasks 4.1-4.3: QA service dispatches by mode and surfaces failure_reason."""
import importlib

from fastapi.testclient import TestClient


def _make_app(monkeypatch, mode: str):
    monkeypatch.setenv("BRIEFALPHA_MODE", mode)
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_REDIS", "1")
    if mode == "live":
        # Force provider=anthropic so the precondition's provider-specific
        # key check (which now matches BRIEFALPHA_LLM_PROVIDER, not "any")
        # picks up the ANTHROPIC_API_KEY we set below.
        monkeypatch.setenv("BRIEFALPHA_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        from briefalpha_api.settings import get_settings as _gs
        _gs.cache_clear()
        import briefalpha_api.config.live_preconditions as lp_mod
        from pathlib import Path
        import tempfile
        td = tempfile.mkdtemp()
        monkeypatch.setattr(lp_mod, "SECRETS_DIR", Path(td))
        # SEC UA is now read from data_sources.yml (not env), and the
        # default contains "example.com" which is rejected. Point the
        # precondition module at a tmp YAML with a real UA.
        ua_yaml = Path(td) / "data_sources.yml"
        ua_yaml.write_text("sec:\n  user_agent: 'BriefAlpha/dev ci@mycompany.com'\n")
        monkeypatch.setattr(lp_mod, "_DATA_SOURCES_PATH", ua_yaml)
    import briefalpha_api.main
    importlib.reload(briefalpha_api.main)
    from briefalpha_api.main import app
    return app


def test_demo_mode_prebaked_response(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        body = client.post("/api/qa", json={
            "brief_id": "2026-04-25",
            "scope": "global",
            "question": "hi",
        }).json()
        assert body["failure_reason"] == "demo_mode_prebaked"
        assert body["is_demo_response"] is True
        assert "demo" in body["answer"].lower()
        assert body["validation_passed"] is True


def test_demo_mode_no_match(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        body = client.post("/api/qa", json={
            "brief_id": "2026-04-25",
            "scope": "global",
            "question": "asdfqwerty xyzzy plugh",
        }).json()
        assert body["failure_reason"] == "demo_mode_no_match"
        assert body["is_demo_response"] is False
        assert "demo" in body["answer"]


def test_empty_question_short_circuits(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        body = client.post("/api/qa", json={
            "brief_id": "2026-04-25",
            "scope": "global",
            "question": "   ",
        }).json()
        assert body["failure_reason"] == "empty_question"
