"""Drawer alignment: when the cached brief carries only a top-3 teaser
trail but the database has the full evidence pool, the drawer endpoint
must return the DB rows — not the teaser. Otherwise clicking
"查看全部 N 条原文" silently returns the same 3 rows the front page
already showed, which broke the user's trust in the source-health table
on the same row of the layout.
"""
from __future__ import annotations

import importlib
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from briefalpha_api.db.models import Evidence
from briefalpha_api.db.session import SessionLocal


def _make_live_app(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "live")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_SCHEDULER", "1")
    monkeypatch.setenv("BRIEFALPHA_DISABLE_REDIS", "1")
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


async def _seed_evidence(brief_id: str, count: int) -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as s:
        for i in range(count):
            s.add(
                Evidence(
                    evidence_id=f"{brief_id}-ev{i}",
                    brief_id=brief_id,
                    source_tier="news",
                    source_reliability=0.6,
                    title=f"news {i}",
                    excerpt=f"excerpt {i}",
                    quote_span=None,
                    detected_tickers=[],
                    chunk_type=None,
                    asset_class=None,
                    exposure_bucket=None,
                    published_at=now,
                    fetched_at=now,
                    base_score=0.5,
                    final_impact_score=0.4,
                    score_breakdown={"source_name": "finnhub"},
                    selected_for_llm=True,
                    conflict=False,
                    requires_review=False,
                    supplementary_sources=[],
                    raw_source_url=None,
                )
            )
        await s.commit()


@pytest.mark.asyncio
async def test_drawer_returns_full_db_pool_not_front_page_teaser(monkeypatch):
    brief_id = "drawer-align-2026-04-27"
    await _seed_evidence(brief_id, count=5)

    app = _make_live_app(monkeypatch)
    with TestClient(app) as client:
        body = client.get(f"/api/evidence/trail?brief_id={brief_id}").json()

    # Drawer must mirror what's actually persisted for the brief — the
    # earlier shortcut returned a 2-3-row teaser from the brief cache,
    # making "查看全部 5 条原文" silently render only 2 rows.
    assert body["evidence_total"] == 5, f"got {body['evidence_total']}"
    assert len(body["evidence_trail"]) == 5
    assert {r["source_tier"] for r in body["evidence_trail"]} == {"news"}
