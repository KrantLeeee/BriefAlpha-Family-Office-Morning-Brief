"""Task 6.5: GET /api/evidence/trail.

Demo mode returns the fixture's `deep_read.evidence_trail` (with each
row stamped `source_tier="demo"`); live mode reads from the DB and
returns an empty list when there are no rows for the brief.
"""
import importlib

from fastapi.testclient import TestClient


def _make_app(monkeypatch, mode="demo"):
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


def test_demo_evidence_trail_returns_fixture(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        body = client.get("/api/evidence/trail?brief_id=2026-04-25").json()
        assert "evidence_trail" in body
        assert "evidence_total" in body
        assert body["evidence_total"] == 20  # fixture's hardcoded total
        assert len(body["evidence_trail"]) >= 1
        for row in body["evidence_trail"]:
            assert "timestamp" in row
            assert "label" in row
            assert row["source_tier"] == "demo"


def test_live_evidence_trail_empty_when_no_db_rows(monkeypatch):
    app = _make_app(monkeypatch, "live")
    with TestClient(app) as client:
        body = client.get("/api/evidence/trail?brief_id=does-not-exist").json()
        assert body["evidence_trail"] == []
        assert body["evidence_total"] == 0


def test_brief_id_required(monkeypatch):
    app = _make_app(monkeypatch, "demo")
    with TestClient(app) as client:
        r = client.get("/api/evidence/trail")
        assert r.status_code == 422
