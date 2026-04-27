"""Regression: Stage B output must be re-aliased before Stage C prompt."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from briefalpha_api.ingestion.base import RawItem
from briefalpha_api.llm import providers as providers_mod
from briefalpha_api.llm.schema import LlmRequest, LlmResponse
from briefalpha_api.pipeline.run import run_pipeline
from briefalpha_api.portfolio.models import PortfolioPosition


@pytest.mark.asyncio
async def test_stage_c_prompt_scrubs_stage_b_real_tickers(monkeypatch) -> None:
    """Stage B responses are reverse-aliased for the final artifact, but
    Stage C is another LLM input boundary. Real tickers must not cross it.
    """

    async def fake_ingestion(_universe):
        now = datetime.now(timezone.utc)
        return {
            "news": [
                RawItem(
                    source_name="unit_news",
                    source_tier="news",
                    source_url="https://example.test/msft-cloud",
                    title="MSFT cloud demand improves",
                    excerpt="MSFT cloud demand improves as enterprise software spending stabilizes.",
                    detected_tickers=["MSFT"],
                    asset_class="us_equity",
                    published_at=now,
                    fetched_at=now,
                ),
                RawItem(
                    source_name="unit_news",
                    source_tier="news",
                    source_url="https://example.test/msft-capex",
                    title="Microsoft capex comments steady",
                    excerpt="Microsoft capex comments remain steady after supplier checks.",
                    detected_tickers=["MSFT"],
                    asset_class="us_equity",
                    published_at=now,
                    fetched_at=now,
                ),
            ]
        }

    import briefalpha_api.pipeline.run as run_mod

    monkeypatch.setattr(run_mod, "run_ingestion", fake_ingestion)

    async def provider(req: LlmRequest, *, provider: str = "anthropic") -> LlmResponse:
        ids = [e.evidence_id for e in req.aliased_evidence[:2]]
        if req.scope == "stage_a":
            structured: dict[str, Any] = {
                "base_case_headline": "cloud demand watch",
                "summary": "enterprise software spending is stabilizing",
                "cited_evidence_ids": ids,
            }
        elif req.scope == "stage_b":
            structured = {
                "judgements": [
                    {
                        "rank": 1,
                        "level": "watch",
                        "title": "MSFT cloud demand stabilizes",
                        "reasoning_chain": {
                            "observed": "MSFT cloud demand improves",
                            "portfolio_exposure": "software exposure",
                            "inference": "spending pressure may ease",
                            "conclusion": "watch US software beta",
                        },
                        "cited_evidence_ids": ids,
                    }
                ]
            }
        else:
            body = json.dumps(req.model_dump(), ensure_ascii=False, default=str)
            assert "MSFT" not in body
            assert "Microsoft" not in body
            structured = {"playbook_events": []}
        return LlmResponse(
            text=json.dumps(structured, ensure_ascii=False),
            structured=structured,
            cited_evidence_ids=structured.get("cited_evidence_ids", []),
            provider="patched",
            model="patched-text",
            template_version=req.template_version,
            latency_ms=0,
            finish_reason="stub",
        )

    monkeypatch.setattr(providers_mod, "call_text_provider", provider)

    out = await run_pipeline(
        brief_id="stage-c-anonymization-2026-04-27",
        positions=[
            PortfolioPosition(
                ticker="MSFT",
                weight=0.25,
                asset_class="us_equity",
                sector="Information Technology",
            ),
            PortfolioPosition(
                ticker="AAPL",
                weight=0.25,
                asset_class="us_equity",
                sector="Information Technology",
            ),
            PortfolioPosition(
                ticker="NVDA",
                weight=0.25,
                asset_class="us_equity",
                sector="Information Technology",
            ),
            PortfolioPosition(
                ticker="0700.HK",
                weight=0.25,
                asset_class="hk_equity",
                sector="Communication Services",
            ),
        ],
        watchlist=[],
    )

    assert out["stage_c"] == {"playbook_events": []}
