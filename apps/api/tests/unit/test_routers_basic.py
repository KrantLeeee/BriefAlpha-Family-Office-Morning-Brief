"""End-to-end-ish HTTP smoke tests that don't require redis or the scheduler.

Uses FastAPI's TestClient so route wiring + dependency injection are
exercised. The lifespan startup is gated by `BRIEFALPHA_DISABLE_SCHEDULER=1`
already set in conftest, plus we mark the secrets check skipped via the
existing env flag.
"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from briefalpha_api.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_brief_today_serves_fixture_when_cache_cold() -> None:
    with TestClient(app) as client:
        r = client.get("/api/brief/today")
    assert r.status_code == 200
    body = r.json()
    # Either the fixture (stale=True) or a freshly generated brief landed.
    assert "brief_id" in body
    assert "judgements" in body


def test_judgement_drawer_404_for_unknown_id() -> None:
    with TestClient(app) as client:
        r = client.get("/api/judgement/nonexistent/drawer")
    assert r.status_code == 404
    assert r.json()["detail"]["error"]["code"] == "judgement_not_found"


def test_portfolio_requires_admin_token() -> None:
    with TestClient(app) as client:
        r = client.get("/api/portfolio")
    assert r.status_code == 401
    assert r.json()["detail"]["error"]["code"] == "missing_admin_token"


def test_portfolio_accepts_admin_token() -> None:
    with TestClient(app) as client:
        r = client.get(
            "/api/portfolio", headers={"Authorization": "Bearer test-admin"}
        )
    assert r.status_code == 200
    assert "tiles" in r.json()


def test_portfolio_rejects_wrong_admin_token() -> None:
    with TestClient(app) as client:
        r = client.get(
            "/api/portfolio", headers={"Authorization": "Bearer wrong-token"}
        )
    assert r.status_code == 403


def test_admin_diagnostics_require_token() -> None:
    with TestClient(app) as client:
        r = client.get("/api/admin/diagnostics/source-health-history")
    assert r.status_code == 401


def test_admin_audit_mode_toggle_requires_twin_token_match() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/admin/audit-mode",
            headers={"Authorization": "Bearer test-admin"},
            json={
                "mode": "compliance",
                "confirm_token": "wrong-but-long-enough",
                "reason": "compliance test mode toggle",
            },
        )
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "confirm_token_mismatch"


def test_admin_audit_mode_toggle_records_with_correct_twin_token() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/admin/audit-mode",
            headers={"Authorization": "Bearer test-admin"},
            json={
                "mode": "compliance",
                "confirm_token": "test-admin",
                "reason": "compliance test mode toggle reason",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["requested_mode"] == "compliance"


def test_research_upload_rejects_non_pdf() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/research/upload",
            files={"file": ("not.txt", io.BytesIO(b"hello"), "text/plain")},
        )
    assert r.status_code == 415
    assert r.json()["detail"]["error"]["code"] == "unsupported_media_type"


def test_analytics_post_persists_events() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/api/_analytics",
            json={
                "events": [
                    {
                        "event_name": "drawer_close",
                        "user_id": "demo",
                        "brief_id": "2026-04-25",
                        "duration_ms": 4200,
                        "close_method": "esc",
                    }
                ]
            },
        )
        assert r.status_code == 200
        assert r.json()["received"] == 1

        recent = client.get("/api/_analytics/recent")
        assert recent.status_code == 200
        names = [e["event_name"] for e in recent.json()["events"]]
        assert "drawer_close" in names


def test_qa_returns_demo_no_match_in_default_demo_mode() -> None:
    """Default mode is demo; arbitrary questions without keyword match go
    through the demo dispatch and return failure_reason=demo_mode_no_match.
    The brief_expired path is now only reachable in live mode."""
    with TestClient(app) as client:
        r = client.post(
            "/api/qa",
            json={
                "brief_id": "never-existed-2099-01-01",
                "scope": "judgement",
                "scope_target_id": "j1",
                "question": "为什么报道的数字不同？",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["failure_reason"] == "demo_mode_no_match"
    assert body["is_demo_response"] is False
    assert "demo" in body["answer"]


def test_source_health_returns_payload_shape() -> None:
    with TestClient(app) as client:
        r = client.get("/api/source-health")
    assert r.status_code == 200
    body = r.json()
    # Either redis snapshot, fresh aggregation, or fixture — all share keys.
    assert "rows" in body
    assert "overall" in body or "as_of_hkt" in body
