"""Stage B fallback must surface multi-tier evidence.

Regression for the 2026-04-27 audit-log issue: when Stage B got rejected
by `accuracy:numbers:missing_in_excerpt`, the wrapper returned the
conservative fallback and `_fallback_stage_b_from_evidence` then cited
`selected[:2]`. Under live data those two slots are always yfinance
market quotes (highest `final_impact_score` = 0.56 dominates news 0.42),
so the user saw a single judgement that referenced no news at all even
though 28 news items were in the pool.
"""
from __future__ import annotations

from datetime import datetime, timezone

from briefalpha_api.pipeline import stages
from briefalpha_api.pipeline.run import _fallback_stage_b_from_evidence


def _ev(eid: str, tier: str, *, title: str = "", excerpt: str = "", tickers: list[str] | None = None) -> stages.Evidence:
    return stages.Evidence(
        evidence_id=eid,
        source_tier=tier,
        source_name=tier,
        source_reliability=0.5,
        title=title or f"{tier}-{eid}",
        excerpt=excerpt or f"excerpt for {eid}",
        quote_span=None,
        detected_tickers=tickers or [],
        chunk_type=None,
        asset_class=None,
        exposure_bucket=None,
        published_at=datetime.now(timezone.utc),
        fetched_at=datetime.now(timezone.utc),
    )


def test_fallback_emits_judgement_per_available_tier() -> None:
    """A pool with news+official+market should produce 3 judgements
    (one anchored in each tier) rather than 1 anchored in the top
    market quote."""
    selected = [
        # Market dominates by final_impact_score in real runs and would
        # have monopolized the old `selected[:2]` slice.
        _ev("m1", "market"),
        _ev("m2", "market"),
        _ev("m3", "market"),
        _ev("n1", "news", title="GDELT headline"),
        _ev("o1", "official", title="SEC filing"),
    ]
    out = _fallback_stage_b_from_evidence(selected, no_direct_portfolio_link=False)
    judgements = out["judgements"]

    # 3 judgements covering news / official / market.
    assert len(judgements) == 3
    primary_titles = [j["title"] for j in judgements]
    assert any("GDELT" in t for t in primary_titles), primary_titles
    assert any("SEC" in t for t in primary_titles), primary_titles


def test_fallback_anchors_in_news_before_market() -> None:
    """Tier priority: human-readable narrative tiers (news/official/research)
    come before market price ticks so the lead judgement is never just
    `0700.HK 隔夜估算 478.60`."""
    selected = [
        _ev("m1", "market", title="0700.HK 隔夜估算 478.60"),
        _ev("n1", "news", title="腾讯 Q3 业绩公告解读"),
    ]
    out = _fallback_stage_b_from_evidence(selected, no_direct_portfolio_link=False)
    judgements = out["judgements"]

    assert judgements[0]["title"].endswith("腾讯 Q3 业绩公告解读")


def test_fallback_judgement_cites_two_distinct_tiers() -> None:
    """Each fallback judgement must cite ≥ 2 evidences AND prefer a
    supporting evidence from a different tier than its primary so the
    UI's evidence drawer surfaces multi-source provenance."""
    selected = [
        _ev("n1", "news"),
        _ev("m1", "market"),
        _ev("o1", "official"),
    ]
    out = _fallback_stage_b_from_evidence(selected, no_direct_portfolio_link=False)
    for j in out["judgements"]:
        assert len(j["cited_evidence_ids"]) == 2
        # Find the evidence rows referenced.
        cited_evs = [e for e in selected if e.evidence_id in j["cited_evidence_ids"]]
        tiers = {e.source_tier for e in cited_evs}
        assert len(tiers) >= 2, f"judgement {j['title']} cites only {tiers}"


def test_fallback_handles_single_tier_pool_gracefully() -> None:
    """If only one tier is available (e.g. ingestion fully degraded),
    we still emit at least one judgement with two citations."""
    selected = [_ev("m1", "market"), _ev("m2", "market")]
    out = _fallback_stage_b_from_evidence(selected, no_direct_portfolio_link=True)
    judgements = out["judgements"]
    assert len(judgements) >= 1
    assert len(judgements[0]["cited_evidence_ids"]) == 2
    assert judgements[0]["requires_review"] is True


def test_fallback_empty_selected_returns_empty_judgements() -> None:
    out = _fallback_stage_b_from_evidence([], no_direct_portfolio_link=False)
    assert out == {"judgements": []}


def test_fallback_writes_specific_reason_and_note_for_numbers_failure() -> None:
    """When the LLM was rejected by the numbers validator, the fallback
    must write a `review.reason="source_conflict"` (closest enum slot) and
    a note that explains *why* AI didn't produce this judgement and which
    evidence was used as the placeholder anchor. The empty `data_gap`
    note shown before this fix told the user nothing actionable."""
    selected = [
        _ev("n1", "news", title="Tencent earnings beat"),
        _ev("o1", "official", title="SEC 10-K filing"),
    ]
    out = _fallback_stage_b_from_evidence(
        selected,
        no_direct_portfolio_link=False,
        last_failure="accuracy:numbers:missing_in_excerpt:[(57006000000.0, 'usd')]",
    )
    j = out["judgements"][0]
    assert j["review"]["kind"] == "fallback"
    assert j["review"]["reason"] == "source_conflict"
    note = j["review"]["note"]
    assert "AI 未生成" in note
    assert "数字" in note  # human-readable failure summary
    # Note should reference the cited evidence titles so the user can locate them.
    assert "Tencent earnings beat" in note or "SEC 10-K filing" in note


def test_fallback_without_failure_info_uses_data_gap() -> None:
    """When the wrapper didn't surface a specific failure (e.g. provider
    crashed before any validator ran), reason falls back to data_gap."""
    selected = [_ev("n1", "news"), _ev("o1", "official")]
    out = _fallback_stage_b_from_evidence(selected, no_direct_portfolio_link=False)
    j = out["judgements"][0]
    assert j["review"]["reason"] == "data_gap"
    assert j["review"]["kind"] == "fallback"
