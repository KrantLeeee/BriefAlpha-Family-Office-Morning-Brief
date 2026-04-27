"""Per-tier minimum quotas in `evidence_selection`.

Without quotas, a brief that has loaded many research uploads ends up with
the LLM seeing 100% market+research evidence: news and official rows fall
just below research on `final_impact_score` (research's higher materiality
edges out news by ~0.005), so the top-K cuts them off entirely. Reserving
a per-tier floor keeps news / official / market visible to the LLM even
when research dominates by volume.
"""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from briefalpha_api.pipeline.stages import Evidence, evidence_selection


def _ev(eid: str, tier: str, score: float) -> Evidence:
    now = datetime.now(UTC)
    return Evidence(
        evidence_id=eid,
        source_tier=tier,
        source_name=tier,
        source_reliability=0.5,
        title=f"{tier}-{eid}",
        excerpt=f"{tier} excerpt {eid}",
        quote_span=None,
        detected_tickers=[],
        chunk_type=None,
        asset_class=None,
        exposure_bucket=None,
        published_at=now,
        fetched_at=now,
        final_impact_score=score,
    )


def test_research_flood_does_not_starve_news_and_official() -> None:
    """Reproduces the live-mode bug: 743 research chunks + 28 finnhub news +
    50 sec_edgar + 16 yfinance was producing 10 yfinance + 10 research, with
    zero news / official reaching the LLM prompt."""
    pool: list[Evidence] = []
    pool += [_ev(f"m{i}", "market", 0.56) for i in range(10)]
    pool += [_ev(f"mw{i}", "market", 0.224) for i in range(6)]
    pool += [_ev(f"r{i}", "research", 0.425) for i in range(743)]
    pool += [_ev(f"n{i}", "news", 0.42) for i in range(28)]
    pool += [_ev(f"o{i}", "official", 0.36) for i in range(50)]

    result = evidence_selection(pool)

    selected = [e for e in result if e.selected_for_llm]
    by_tier = Counter(e.source_tier for e in selected)

    assert len(selected) == 20, "top_k contract preserved"
    assert by_tier["news"] >= 5, f"news floor violated: {by_tier}"
    assert by_tier["official"] >= 3, f"official floor violated: {by_tier}"
    assert by_tier["market"] >= 3, f"market floor violated: {by_tier}"


def test_floor_does_not_pad_when_tier_short() -> None:
    """If a tier has fewer items than its floor, take what's there. No
    placeholder rows, no double-counting from other tiers."""
    pool: list[Evidence] = []
    pool += [_ev(f"r{i}", "research", 0.5) for i in range(40)]
    pool += [_ev("n0", "news", 0.42), _ev("n1", "news", 0.40)]  # only 2 news

    result = evidence_selection(pool)
    selected = [e for e in result if e.selected_for_llm]
    by_tier = Counter(e.source_tier for e in selected)

    assert by_tier["news"] == 2
    assert len(selected) == 20


def test_floor_does_not_overshoot_top_k_when_floors_sum_high() -> None:
    """Defensive: if caller passes floors summing past top_k, the trim
    keeps only the highest-scoring `top_k` selections — never more."""
    pool: list[Evidence] = []
    pool += [_ev(f"m{i}", "market", 0.8) for i in range(15)]
    pool += [_ev(f"n{i}", "news", 0.5) for i in range(15)]
    pool += [_ev(f"o{i}", "official", 0.3) for i in range(15)]

    result = evidence_selection(
        pool,
        top_k=10,
        tier_floors={"market": 5, "news": 5, "official": 5},  # sums to 15 > 10
    )
    selected = [e for e in result if e.selected_for_llm]
    assert len(selected) == 10
