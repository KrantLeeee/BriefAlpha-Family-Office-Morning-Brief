"""End-to-end integration tests for `pipeline.run.run_full_brief`.

These tests exercise the full Mainline-A wiring (ingestion → 9 stages →
anonymization → stage A/B/C via stub LLM → artifact assembly) using the
deterministic stub provider. They are HERMETIC:
  * no external network expected (yfinance / GDELT / NewsAPI fail-soft);
  * settings is steered at a tmp sqlite DB by the root conftest;
  * AES-GCM alias_key + stub LLM keys file are provisioned in conftest.

The stub provider serves a fixed JSON for stage_a (with 2 citations) and
empty stage_b/stage_c — enough to traverse `build_brief_artifact` without
real keys.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from briefalpha_api.db.models import Portfolio
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.pipeline.artifact import build_brief_artifact
from briefalpha_api.pipeline.run import run_full_brief

BRIEF_ID = "test-brief-2026-04-25"

REQUIRED_TOP_LEVEL_KEYS: set[str] = {
    "brief_id",
    "brief_date_hkt",
    "delivered_at_hkt",
    "freeze_window_hkt",
    "stale",
    "audit_mode",
    "anonymized",
    "no_direct_portfolio_link",
    "conservative",
    "degraded_sources",
    "base_case",
    "portfolio_snapshot",
    "judgements",
    "playbook_events",
    "deep_read",
    "macro_pulse_collapsed",
    "footer",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _reset_portfolio() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Portfolio))
        await s.commit()


async def _seed_balanced_portfolio() -> None:
    """A 4-position portfolio that passes k=3 (≥3 sectors filled by decoys
    via universe.build_universe)."""
    async with SessionLocal() as s:
        await s.execute(delete(Portfolio))
        rows = [
            Portfolio(
                user_id="demo",
                ticker="NVDA",
                weight=0.25,
                asset_class="us_equity",
                sector="Information Technology",
            ),
            Portfolio(
                user_id="demo",
                ticker="AAPL",
                weight=0.25,
                asset_class="us_equity",
                sector="Information Technology",
            ),
            Portfolio(
                user_id="demo",
                ticker="MSFT",
                weight=0.25,
                asset_class="us_equity",
                sector="Information Technology",
            ),
            Portfolio(
                user_id="demo",
                ticker="0700.HK",
                weight=0.25,
                asset_class="hk_equity",
                sector="Communication Services",
            ),
        ]
        for r in rows:
            s.add(r)
        await s.commit()


async def _seed_tiny_portfolio() -> None:
    """A 2-position portfolio in a single sector — bucket has < k=3 members
    so `cold_start_passed` flips to False and `no_direct_portfolio_link`
    is forced True."""
    async with SessionLocal() as s:
        await s.execute(delete(Portfolio))
        rows = [
            Portfolio(
                user_id="demo",
                ticker="NVDA",
                weight=0.5,
                asset_class="us_equity",
                sector="Information Technology",
            ),
            Portfolio(
                user_id="demo",
                ticker="AAPL",
                weight=0.5,
                asset_class="us_equity",
                sector="Information Technology",
            ),
        ]
        for r in rows:
            s.add(r)
        await s.commit()


# ---------------------------------------------------------------------------
# 1. Smoke: full pipeline returns a frontend-shaped Brief
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_full_brief_smoke() -> None:
    await _seed_balanced_portfolio()
    try:
        artifact = await run_full_brief(BRIEF_ID)
    finally:
        await _reset_portfolio()

    assert isinstance(artifact, dict)
    missing = REQUIRED_TOP_LEVEL_KEYS - set(artifact.keys())
    assert not missing, f"missing top-level keys: {missing}"

    assert artifact["brief_id"] == BRIEF_ID
    assert artifact["stale"] is False
    assert artifact["audit_mode"] == "demo"
    assert artifact["anonymized"] is True

    base_case = artifact["base_case"]
    for k in ("headline", "summary", "estimate_value"):
        assert k in base_case, f"base_case missing key {k}"
    # estimate_value is always a string ending with %.
    assert isinstance(base_case["estimate_value"], str)
    assert base_case["estimate_value"].endswith("%")

    snapshot = artifact["portfolio_snapshot"]
    assert isinstance(snapshot.get("tiles"), list)
    assert len(snapshot["tiles"]) > 0, "portfolio_snapshot.tiles should be non-empty"
    # Sanity: all tiles in our seeded set should appear.
    seen_tickers = {t["ticker"] for t in snapshot["tiles"]}
    assert "NVDA" in seen_tickers


# ---------------------------------------------------------------------------
# 2. Artifact builder strips secrets / extra keys
# ---------------------------------------------------------------------------


def test_artifact_strips_secrets() -> None:
    """`build_brief_artifact` should ignore any unexpected fields in the
    pipeline output and produce a Brief that exposes only contract keys.
    """
    rogue_pipeline_output: dict = {
        "brief_id": "shape-test",
        "brief_date_hkt": "shape-test",
        "no_direct_portfolio_link": False,
        "conservative": False,
        "stage_a": {
            "base_case_headline": "headline",
            "summary": "summary",
            "cited_evidence_ids": ["e1", "e2"],
        },
        "stage_b": {"judgements": []},
        "stage_c": {"playbook_events": []},
        "evidence_pool_full": [
            {
                "evidence_id": "e1",
                "source_tier": "official",
                "source_name": "sec_edgar",
                "title": "Earnings 8-K",
                "excerpt": "Revenue beat by 5%",
                # Datetime here mirrors what pipeline.run emits *internally*
                # (the run module converts to isoformat before reaching the
                # artifact, but the builder MUST tolerate either form).
                "published_at": datetime(2026, 4, 25, 12, tzinfo=timezone.utc),
                # Unknown extra key — should be ignored.
                "secret_internal_field": "DO-NOT-LEAK",
            }
        ],
        "selected_evidence_for_llm": [],
        # Unknown top-level extra — must NOT propagate to artifact.
        "internal_debug": {"api_key": "sk-leaked"},
    }

    artifact = build_brief_artifact(
        pipeline_output=rogue_pipeline_output,
        portfolio_positions=[
            {"ticker": "NVDA", "weight": 0.5, "asset_class": "us_equity"},
            {"ticker": "AAPL", "weight": 0.5, "asset_class": "us_equity"},
        ],
        watchlist=[],
        source_health={"overall": "ok", "rows": []},
        quotes={},
    )

    # No leaked extras at the top level.
    assert "internal_debug" not in artifact
    assert "secret_internal_field" not in artifact

    # Required top-level keys still present.
    missing = REQUIRED_TOP_LEVEL_KEYS - set(artifact.keys())
    assert not missing, f"missing required keys: {missing}"

    # Verify nothing leaked to nested dicts either (cheap sanity).
    serialized = repr(artifact)
    assert "DO-NOT-LEAK" not in serialized
    assert "sk-leaked" not in serialized


# ---------------------------------------------------------------------------
# 3. no_direct_portfolio_link propagation when k-anonymity fails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_direct_portfolio_link_propagates() -> None:
    await _seed_tiny_portfolio()
    try:
        artifact = await run_full_brief(BRIEF_ID)
    finally:
        await _reset_portfolio()

    assert (
        artifact["no_direct_portfolio_link"] is True
    ), "k-anonymity failure (2 holdings, single sector) must propagate as no_direct_portfolio_link=True"

    # Top-level shape still intact even in the degraded case.
    missing = REQUIRED_TOP_LEVEL_KEYS - set(artifact.keys())
    assert not missing, f"missing top-level keys: {missing}"
