"""Task 2.3: Wire mode + preconditions into app startup.

Verifies:
- demo mode starts cleanly and stashes mode on app.state
- default (no env var) defaults to demo
- live mode without preconditions fails fast (SystemExit(1))
- live mode with preconditions satisfied starts cleanly
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_demo_mode_starts_cleanly(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "demo")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")

    # Import inside the test so monkeypatch takes effect before app import.
    from briefalpha_api.main import app

    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert app.state.mode == "demo"


def test_default_mode_is_demo(monkeypatch):
    monkeypatch.delenv("BRIEFALPHA_MODE", raising=False)
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")

    from briefalpha_api.main import app

    with TestClient(app) as client:
        client.get("/api/health")
        assert app.state.mode == "demo"


def test_live_mode_fails_fast_when_preconditions_missing(monkeypatch, caplog):
    monkeypatch.setenv("BRIEFALPHA_MODE", "live")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    # Ensure no LLM key is present
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)

    # Point SECRETS_DIR at an empty tmp dir so live preconditions can't find a secrets file.
    import briefalpha_api.config.live_preconditions as lp_mod
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(lp_mod, "SECRETS_DIR", Path(td))

        from briefalpha_api.main import app

        # NOTE: `lifespan` calls `raise SystemExit(1)` synchronously when
        # preconditions fail. anyio 4.x wraps any `BaseException` (incl.
        # `SystemExit`) raised inside its TaskGroups in a `BaseExceptionGroup`,
        # and starlette's `TestClient` uses a `BlockingPortal` whose
        # `.result()` surfaces the failed-startup as `CancelledError` to the
        # caller (the underlying `BaseExceptionGroup[SystemExit(1)]` is logged
        # to stderr by anyio). The exact exception type at this boundary is
        # therefore implementation-defined; what we MUST verify is that
        # `TestClient(app).__enter__` did NOT succeed and that the lifespan
        # actually executed the precondition-fail branch.
        import logging
        with caplog.at_level(logging.ERROR, logger="briefalpha.main"):
            with pytest.raises(BaseException):
                with TestClient(app):
                    pass

        # The SystemExit branch logs the precondition issues at ERROR.
        assert any(
            "Live mode preconditions failed" in rec.message
            for rec in caplog.records
        ), (
            "Expected lifespan to log 'Live mode preconditions failed' before "
            f"raising SystemExit(1). caplog: {[r.message for r in caplog.records]}"
        )


def test_live_mode_passes_when_preconditions_satisfied(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIEFALPHA_MODE", "live")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("BRIEFALPHA_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    from briefalpha_api.settings import get_settings as _gs
    _gs.cache_clear()

    import briefalpha_api.config.live_preconditions as lp_mod
    monkeypatch.setattr(lp_mod, "SECRETS_DIR", tmp_path)
    # SEC UA is now read from data_sources.yml (not env). Provide a tmp
    # YAML with a real (non-placeholder) UA.
    ua_yaml = tmp_path / "data_sources.yml"
    ua_yaml.write_text("sec:\n  user_agent: 'BriefAlpha/dev ci@mycompany.com'\n")
    monkeypatch.setattr(lp_mod, "_DATA_SOURCES_PATH", ua_yaml)

    from briefalpha_api.main import app

    with TestClient(app) as client:
        client.get("/api/health")
        assert app.state.mode == "live"
