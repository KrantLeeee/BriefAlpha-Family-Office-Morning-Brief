"""Path B (light): when Stage B cites at least one news evidence, the
numbers validator's `excerpt_text` must include all selected news excerpts
in the brief — not just the cited ones. This is what lets the LLM mention
a market-wide narrative number from one news item while citing a different,
related news headline that does the qualitative anchoring.

Without this expansion, the strict number-discipline rule taught the LLM
to avoid news entirely (see audit log 2026-04-27 → every successful Stage B
cited only yfinance + research).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    SensitiveEntityDictionary,
)
from briefalpha_api.pipeline.run import _make_validator
from briefalpha_api.validator.runner import EvidencePoolEntry


class _FakeResp:
    def __init__(self, structured: dict) -> None:
        self.structured = structured


def _ctx(*, news_excerpts: dict[str, str], non_news_excerpts: dict[str, str]) -> dict:
    excerpt_aliased_by_id = {**news_excerpts, **non_news_excerpts}
    pool_metadata = {
        eid: EvidencePoolEntry(source_tier="news", asset_class=None, published_at=datetime.now(timezone.utc))
        for eid in news_excerpts
    } | {
        eid: EvidencePoolEntry(source_tier="research", asset_class=None, published_at=datetime.now(timezone.utc))
        for eid in non_news_excerpts
    }
    return {
        "scope": "stage_b",
        "pool_ids": set(excerpt_aliased_by_id.keys()),
        "pool_metadata": pool_metadata,
        "excerpt_aliased_by_id": excerpt_aliased_by_id,
        "quote_segments_by_id": {},
        "sensitive_dict": SensitiveEntityDictionary(),
        "brief_freeze_at_hkt": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_news_cite_expands_excerpt_with_other_selected_news() -> None:
    """A judgement citing news_a should pass numbers validation even when
    the only matching number lives in news_b — both belong to the same
    Stage B selected pool."""
    validator = _make_validator(
        **_ctx(
            news_excerpts={
                "news_a": "Tencent Q3 revenue up year over year, narrative without precise %.",
                "news_b": "数据中心营收下调 8% 主因企业端需求趋缓",
            },
            non_news_excerpts={
                "research_a": "research excerpt with no relevant numbers",
            },
        )
    )
    structured = {
        "judgements": [
            {
                "rank": 1,
                "level": "watch",
                "title": "数据中心需求承压",
                "reasoning_chain": {
                    "observed": "数据中心营收下调 8%。",
                    "portfolio_exposure": "AI 算力相关持仓承压。",
                    "inference": "企业资本开支放缓。",
                    "conclusion": "进入观察。",
                },
                # Cite news_a only — the 8% lives in news_b, not in news_a.
                # Without the expansion, this would fail numbers validation.
                "cited_evidence_ids": ["news_a", "research_a"],
            }
        ]
    }
    ok, reason = await validator(_FakeResp(structured))
    assert ok, reason


@pytest.mark.asyncio
async def test_no_news_cited_keeps_strict_numbers_check() -> None:
    """If the LLM cites zero news evidences, the news-pool expansion must
    NOT kick in — otherwise we'd silently weaken validation for every
    research-only or market-only judgement."""
    validator = _make_validator(
        **_ctx(
            news_excerpts={
                "news_a": "Tencent Q3 revenue up.",
                "news_b": "数据中心营收下调 8%",
            },
            non_news_excerpts={
                "research_a": "research excerpt with no 8 percent figure.",
                "research_b": "another research excerpt with no relevant figure.",
            },
        )
    )
    structured = {
        "judgements": [
            {
                "rank": 1,
                "level": "watch",
                "title": "research-only judgement",
                "reasoning_chain": {
                    "observed": "数据中心营收下调 8%。",  # 8% is not in research_a
                    "portfolio_exposure": "—",
                    "inference": "—",
                    "conclusion": "—",
                },
                "cited_evidence_ids": ["research_a", "research_b"],
            }
        ]
    }
    ok, reason = await validator(_FakeResp(structured))
    assert not ok
    assert "numbers" in (reason or "")


@pytest.mark.asyncio
async def test_news_expansion_cannot_rescue_truly_hallucinated_numbers() -> None:
    """The expansion only widens the excerpt context to other news items
    in the same selected pool. A number that exists in NO selected news
    AND no cited evidence must still fail."""
    validator = _make_validator(
        **_ctx(
            news_excerpts={
                "news_a": "Tencent Q3 revenue up.",
                "news_b": "数据中心营收下调 5%",
            },
            non_news_excerpts={
                "research_a": "no relevant numbers",
            },
        )
    )
    structured = {
        "judgements": [
            {
                "rank": 1,
                "level": "watch",
                "title": "made-up number",
                "reasoning_chain": {
                    "observed": "毛利率扩张 18%",  # 18% appears nowhere
                    "portfolio_exposure": "—",
                    "inference": "—",
                    "conclusion": "—",
                },
                "cited_evidence_ids": ["news_a", "research_a"],
            }
        ]
    }
    ok, reason = await validator(_FakeResp(structured))
    assert not ok
    assert "18" in (reason or "")
