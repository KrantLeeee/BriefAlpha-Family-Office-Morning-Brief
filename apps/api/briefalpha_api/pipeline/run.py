"""run_brief: orchestrate the 9 stages + 3 LLM stages.

Conservative-brief trigger conditions (PRD §5.1.3 / task 10.3):
  1. evidence_pool_full empty
  2. all text-LLM providers fail
  3. accuracy_validator fails 3 times in a row for the same brief

k=3 / cold_start failure ≠ conservative; that goes through
`no_direct_portfolio_link_fallback`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from briefalpha_api.anonymization import (
    AliasContext,
    build_aliased_evidence,
    encrypt_alias_map,
    make_alias_context,
)
from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    build_sensitive_entity_dictionary,
)
from briefalpha_api.ingestion.runner import run_ingestion
from briefalpha_api.llm import call_text_llm, conservative_fallback
from briefalpha_api.llm.prompt_builder import build_request
from briefalpha_api.pipeline import stages
from briefalpha_api.portfolio.models import PortfolioPosition, PrivacySafeUniverse
from briefalpha_api.portfolio.universe import build_universe


async def run_pipeline(
    *,
    brief_id: str,
    positions: list[PortfolioPosition],
    watchlist: list[str],
) -> dict[str, Any]:
    universe, bucket_summary = build_universe(
        brief_id=brief_id, positions=positions, watchlist=watchlist
    )
    no_direct_portfolio_link = (
        not bucket_summary.cold_start_passed
        or all(b.is_other_equity_pool for b in bucket_summary.buckets)
    )

    raw_by_source = await run_ingestion(universe)
    raw_items = [item for items in raw_by_source.values() for item in items]

    freeze_at = datetime.now(timezone.utc)
    ev = stages.normalize(brief_id, raw_items)
    ev = stages.entity_linking(ev, universe.ticker_set())
    ev = stages.dedupe(ev)
    ev = stages.base_scoring(ev, brief_freeze_at=freeze_at)
    ev = stages.portfolio_mapping(ev, bucket_summary)
    ev = stages.conflict_resolve(ev)
    ev = stages.final_scoring(ev, no_direct_portfolio_link=no_direct_portfolio_link)
    ev = stages.evidence_selection(ev)

    selected = [e for e in ev if e.selected_for_llm]

    if not ev:
        # Conservative trigger 1: evidence pool empty.
        return _conservative_artifact(brief_id)

    # Anonymization stage
    sensitive_dict = build_sensitive_entity_dictionary(
        universe_tickers=[t.ticker for t in universe.tickers]
    )
    ctx = make_alias_context(
        brief_id=brief_id,
        universe_tickers=[t.ticker for t in universe.tickers],
        entity_dictionary=sensitive_dict,
    )
    aliased = []
    for e in selected:
        ae, _segs = build_aliased_evidence(
            evidence_id=e.evidence_id,
            title=e.title,
            excerpt=e.excerpt,
            source_tier=e.source_tier,  # type: ignore[arg-type]
            asset_class=e.asset_class,
            published_at=e.published_at,
            ctx=ctx,
            quote_span_original=e.quote_span,
        )
        aliased.append(ae)

    # Persist alias map (encrypted, brief-scoped)
    encrypt_alias_map(brief_id, ctx)

    # Stage A → C
    audit_ctx = {"brief_id": brief_id, "audit_mode": "demo"}
    stage_a_req = build_request(
        scope="stage_a",
        aliased_evidence=aliased,
        extra_payload={
            "no_direct_portfolio_link": no_direct_portfolio_link,
            "aliased_evidence_json": [a.model_dump() for a in aliased],
        },
    )
    stage_a_resp = await call_text_llm(stage_a_req, audit_ctx=audit_ctx, alias_context=ctx)

    return {
        "brief_id": brief_id,
        "no_direct_portfolio_link": no_direct_portfolio_link,
        "conservative": stage_a_resp.provider == "conservative",
        "stage_a": stage_a_resp.structured,
        "evidence_pool_full": [_evidence_dict(e) for e in ev],
        "selected_evidence_for_llm": [_evidence_dict(e) for e in selected],
    }


def _conservative_artifact(brief_id: str) -> dict[str, Any]:
    return {
        "brief_id": brief_id,
        "conservative": True,
        "stage_a": conservative_fallback("stage_a").structured,
        "evidence_pool_full": [],
        "selected_evidence_for_llm": [],
    }


def _evidence_dict(ev: stages.Evidence) -> dict[str, Any]:
    return {
        "evidence_id": ev.evidence_id,
        "source_tier": ev.source_tier,
        "source_name": ev.source_name,
        "title": ev.title,
        "excerpt": ev.excerpt,
        "detected_tickers": ev.detected_tickers,
        "asset_class": ev.asset_class,
        "exposure_bucket": ev.exposure_bucket,
        "published_at": ev.published_at.isoformat() if ev.published_at else None,
        "base_score": ev.base_score,
        "final_impact_score": ev.final_impact_score,
        "score_breakdown": ev.score_breakdown,
        "selected_for_llm": ev.selected_for_llm,
        "conflict": ev.conflict,
        "requires_review": ev.requires_review,
        "supplementary_sources": ev.supplementary_sources,
    }


def build_brief_artifact(_pipeline_output: dict) -> dict:
    """Convert pipeline output → frontend-shaped Brief.

    The full mapping (judgements/playbook/portfolio_snapshot composition)
    lives in section 10.1; until provider keys are wired up we return the
    fixture in `routers/brief.py`.
    """
    return _pipeline_output
