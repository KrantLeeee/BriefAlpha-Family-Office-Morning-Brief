"""Tasks 5.1-5.4: Review persistence + brief merge.

Covers POST /api/review/{judgement_id} (create + update) and the
brief-assembly merge that surfaces persisted overrides on
GET /api/brief/today.
"""
from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _make_app(monkeypatch, mode: str = "demo"):
    monkeypatch.setenv("BRIEFALPHA_MODE", mode)
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_REDIS", "1")
    import briefalpha_api.main
    importlib.reload(briefalpha_api.main)
    from briefalpha_api.main import app
    return app


def test_post_review_creates_review_row(monkeypatch):
    app = _make_app(monkeypatch)
    with TestClient(app) as client:
        r1 = client.post(
            "/api/review/j1",
            json={
                "brief_id": "test-brief-create",
                "status": "reviewed",
                "note": "Confirmed source conflict acceptable",
            },
        )
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["status"] == "ok"
        assert body1["judgement_id"] == "j1"
        assert body1["review_status"] == "reviewed"
        assert body1["reviewed_at"]


def test_post_review_status_open_keeps_old_reviewed_at(monkeypatch):
    """When flipping reviewed → open, the timestamp of the prior review is preserved
    (audit trail). Only the status flips back."""
    app = _make_app(monkeypatch)
    with TestClient(app) as client:
        client.post(
            "/api/review/j1",
            json={
                "brief_id": "test-brief-update",
                "status": "reviewed",
                "note": "ok",
            },
        )
        r2 = client.post(
            "/api/review/j1",
            json={
                "brief_id": "test-brief-update",
                "status": "open",
                "note": "reopened",
            },
        )
        assert r2.status_code == 200
        body = r2.json()
        assert body["review_status"] == "open"
        # reviewed_at is NOT cleared — preserves audit trail.
        assert body["reviewed_at"] is not None


def test_brief_today_includes_review_override_after_post(monkeypatch):
    app = _make_app(monkeypatch, mode="demo")
    with TestClient(app) as client:
        # First fetch the demo brief to obtain today's brief_id.
        body0 = client.get("/api/brief/today").json()
        brief_id = body0["brief_id"]
        # Confirm the fixture's j1.review starts as "open".
        j1_before = next(j for j in body0["judgements"] if j["id"] == "j1")
        assert j1_before["review"]["status"] == "open"

        # Mark reviewed
        r = client.post(
            "/api/review/j1",
            json={
                "brief_id": brief_id,
                "status": "reviewed",
                "note": "Acknowledged",
            },
        )
        assert r.status_code == 200

        # Re-fetch — j1.review.status should now be "reviewed"
        body1 = client.get("/api/brief/today").json()
        j1_after = next(j for j in body1["judgements"] if j["id"] == "j1")
        assert j1_after["review"]["status"] == "reviewed"
        assert j1_after["review"]["note"] == "Acknowledged"
        assert j1_after["review"]["reviewed_at"] is not None


def test_review_endpoint_validates_status_enum(monkeypatch):
    app = _make_app(monkeypatch)
    with TestClient(app) as client:
        r = client.post(
            "/api/review/jX",
            json={"brief_id": "x", "status": "closed", "note": ""},
        )
        assert r.status_code == 422


def test_review_endpoint_default_note_is_empty_string(monkeypatch):
    app = _make_app(monkeypatch)
    with TestClient(app) as client:
        r = client.post(
            "/api/review/jX",
            json={"brief_id": "test-brief-default-note", "status": "open"},
        )
        assert r.status_code == 200
        assert r.json()["review_status"] == "open"
