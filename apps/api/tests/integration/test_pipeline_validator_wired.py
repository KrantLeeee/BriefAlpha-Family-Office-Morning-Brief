"""Regression: Stage A/B/C must hand `accuracy_validate` to the wrapper.

Without this, the wrapper would skip the validator step on the main brief
generation path — citations / quote_span / numbers / polarity / time_window
would only run in the offline golden runner. We assert by making the
provider return a response that fails citations (cited_evidence_ids
references an id NOT in the pool); after MAX_RETRY_TEXT attempts the
wrapper MUST return the conservative_fallback shape, which propagates
into `pipeline_output["conservative"] is True`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from sqlalchemy import delete

from briefalpha_api.db.models import Portfolio
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.llm import providers as providers_mod
from briefalpha_api.llm.schema import LlmRequest, LlmResponse
from briefalpha_api.pipeline.run import run_full_brief

BRIEF_ID = "validator-regression-2026-04-26"


async def _seed() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Portfolio))
        s.add_all(
            [
                Portfolio(user_id="demo", ticker="NVDA", weight=0.25, asset_class="us_equity", sector="Information Technology"),
                Portfolio(user_id="demo", ticker="AAPL", weight=0.25, asset_class="us_equity", sector="Information Technology"),
                Portfolio(user_id="demo", ticker="MSFT", weight=0.25, asset_class="us_equity", sector="Information Technology"),
                Portfolio(user_id="demo", ticker="0700.HK", weight=0.25, asset_class="hk_equity", sector="Communication Services"),
            ]
        )
        await s.commit()


async def _purge() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Portfolio))
        await s.commit()


@pytest.mark.asyncio
async def test_main_pipeline_invokes_accuracy_validator(monkeypatch) -> None:
    """If the provider returns a response that fails the citation rule,
    the wrapper MUST exhaust retries and return the conservative
    fallback. We detect this via `pipeline_output["conservative"] is True`.
    """
    await _seed()
    try:
        # Patch the text provider to return a response with a non-existent
        # cited_evidence_id. The validator's `validate_citations` will
        # reject every attempt; after MAX_RETRY_TEXT=3 the wrapper falls
        # back to conservative.
        async def bad_provider(req: LlmRequest, *, provider: str = "anthropic") -> LlmResponse:
            stub = {
                "base_case_headline": "（regression）会被 validator 拒绝",
                "summary": "regression test summary",
                "cited_evidence_ids": ["does_not_exist_in_pool_1", "does_not_exist_in_pool_2"],
                "judgements": [],
                "playbook_events": [],
            }
            import json as _json

            return LlmResponse(
                text=_json.dumps(stub, ensure_ascii=False),
                structured=stub,
                cited_evidence_ids=stub["cited_evidence_ids"],
                provider="patched",
                model="patched-text",
                template_version=req.template_version,
                latency_ms=0,
                finish_reason="stub",
            )

        monkeypatch.setattr(providers_mod, "call_text_provider", bad_provider)

        artifact = await run_full_brief(BRIEF_ID)
    finally:
        await _purge()

    # Conservative fallback should have triggered for at least one stage —
    # which is what proves the validator was wired through the wrapper.
    # The artifact builder propagates `conservative=True` to the top level.
    assert artifact["conservative"] is True, (
        "Stage A/B/C did not invoke accuracy_validate through the wrapper — "
        "validator failures aren't reaching the conservative fallback path. "
        "Check `pipeline.run.run_pipeline` is passing `accuracy_validate` to "
        "every `call_text_llm`."
    )


@pytest.mark.asyncio
async def test_main_pipeline_does_not_fall_back_on_clean_validator(monkeypatch) -> None:
    """Sanity: when the provider returns valid output, the validator
    should pass and conservative MUST stay False."""
    await _seed()
    try:
        async def clean_provider(req: LlmRequest, *, provider: str = "anthropic") -> LlmResponse:
            # The wrapper feeds the request's aliased_evidence in; we cite
            # the first two ids which the validator will accept.
            ids = [e.evidence_id for e in req.aliased_evidence[:2]]
            stub: dict[str, Any] = {
                "base_case_headline": "regression clean",
                "summary": "no hallucinated numbers here",
                "cited_evidence_ids": ids,
                "judgements": [],
                "playbook_events": [],
            }
            import json as _json

            return LlmResponse(
                text=_json.dumps(stub, ensure_ascii=False),
                structured=stub,
                cited_evidence_ids=ids,
                provider="patched-clean",
                model="patched-text",
                template_version=req.template_version,
                latency_ms=0,
                finish_reason="stub",
            )

        monkeypatch.setattr(providers_mod, "call_text_provider", clean_provider)
        artifact = await run_full_brief(BRIEF_ID)
    finally:
        await _purge()

    # Note: stage_b uses citations validator with judgement-level rule,
    # but our clean provider returns judgements=[] which short-circuits the
    # check vacuously. So conservative SHOULD be False overall.
    assert artifact["conservative"] is False, (
        "Validator unexpectedly rejected a clean response — the wired check "
        "may be too strict (e.g. quote_span requires segments we don't pass)."
    )
