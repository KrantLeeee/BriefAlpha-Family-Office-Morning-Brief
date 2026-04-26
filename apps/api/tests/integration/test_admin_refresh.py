"""Task 2.7: /api/admin/data/refresh endpoint."""
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


def test_demo_refresh_returns_demo_refreshed_status(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        resp = client.post("/api/admin/data/refresh")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "demo_refreshed"
        assert body["brief_id"]
        assert body["refreshed_at_hkt"]  # HH:MM string
        assert body["note"] == "示例数据，非实时采集"


def test_live_refresh_returns_queued(monkeypatch):
    app = _make_app(monkeypatch, "live")
    with TestClient(app) as client:
        resp = client.post("/api/admin/data/refresh")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"
        assert body["brief_id"]


def test_demo_refresh_format_of_refreshed_at_hkt(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        body = client.post("/api/admin/data/refresh").json()
        # expect HH:MM with two-digit components
        import re
        assert re.match(r"^\d{2}:\d{2}$", body["refreshed_at_hkt"])
