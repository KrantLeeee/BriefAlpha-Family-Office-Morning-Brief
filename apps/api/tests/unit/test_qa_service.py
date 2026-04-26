"""QA service: brief_expired path + insufficient_evidence path."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from briefalpha_api.anonymization import (
    encrypt_alias_map,
    make_alias_context,
)
from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    build_sensitive_entity_dictionary,
)
from briefalpha_api.db.models import Evidence
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.qa import run_qa
from briefalpha_api.search.fts import index_evidence


async def _purge_evidence() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(Evidence))
        await s.commit()


@pytest.mark.asyncio
async def test_qa_returns_brief_expired_when_alias_map_missing() -> None:
    async with SessionLocal() as s:
        result = await run_qa(
            s,
            brief_id="never-existed-2099-01-01",
            scope="judgement",
            scope_target_id="j1",
            question="为什么报道的数字不同？",
        )
    assert result.failure_reason == "brief_expired"
    assert result.validation_passed is False
    # Frontend renders this verbatim — keep stable.
    assert "过期" in result.answer


@pytest.mark.asyncio
async def test_qa_returns_insufficient_evidence_when_pool_empty() -> None:
    """alias_map exists but FTS+evidence return nothing."""
    await _purge_evidence()
    brief_id = "qa-empty-2026-04-25"
    sensitive_dict = build_sensitive_entity_dictionary(universe_tickers=["NVDA"])
    ctx = make_alias_context(
        brief_id=brief_id,
        universe_tickers=["NVDA"],
        entity_dictionary=sensitive_dict,
    )
    encrypt_alias_map(brief_id, ctx)

    async with SessionLocal() as s:
        result = await run_qa(
            s,
            brief_id=brief_id,
            scope="global",
            scope_target_id=None,
            question="今天最值得关注的研判是什么？",
        )
    assert result.insufficient_evidence is True
    assert result.cited_evidence_ids == []


@pytest.mark.asyncio
async def test_qa_with_evidence_returns_answer_and_cites() -> None:
    """Smoke: stub LLM cites the first 2 ev ids; run_qa rebuilds AliasedEvidence."""
    await _purge_evidence()
    brief_id = "qa-smoke-2026-04-25"
    sensitive_dict = build_sensitive_entity_dictionary(universe_tickers=["NVDA"])
    ctx = make_alias_context(
        brief_id=brief_id,
        universe_tickers=["NVDA"],
        entity_dictionary=sensitive_dict,
    )
    encrypt_alias_map(brief_id, ctx)

    now = datetime.now(timezone.utc)
    async with SessionLocal() as s:
        for idx in range(2):
            ev = Evidence(
                evidence_id=f"ev_qa_{idx}",
                brief_id=brief_id,
                source_tier="news",
                source_reliability=0.6,
                title=f"QA 测试 evidence #{idx}",
                excerpt=f"NVDA 数据中心营收下调 {8 + idx}%",
                quote_span=None,
                detected_tickers=["NVDA"],
                chunk_type="text",
                asset_class="us_equity",
                exposure_bucket=None,
                published_at=now,
                fetched_at=now,
                base_score=0.8,
                final_impact_score=0.6,
                score_breakdown={},
                selected_for_llm=True,
                conflict=False,
                requires_review=False,
                supplementary_sources=[],
                raw_source_url=None,
            )
            s.add(ev)
            await index_evidence(
                s,
                evidence_id=ev.evidence_id,
                brief_id=brief_id,
                title=ev.title,
                excerpt=ev.excerpt,
                detected_tickers=["NVDA"],
                chunk_type="text",
                source_tier="news",
            )
        await s.commit()

    async with SessionLocal() as s:
        # FTS5 unicode61 with the default tokenizer treats "NVDA" as one
        # token; querying it MUSTmatch both seeded rows.
        result = await run_qa(
            s,
            brief_id=brief_id,
            scope="global",
            scope_target_id=None,
            question="NVDA",
        )
    # Stub provider returns up to 2 cited ids it sees in the aliased_evidence input.
    assert result.validation_passed is True
    assert not result.insufficient_evidence
    assert len(result.cited_evidence_ids) >= 1
    assert all(eid in {"ev_qa_0", "ev_qa_1"} for eid in result.cited_evidence_ids)
