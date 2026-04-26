"""audit.writer integration: each LLM-wrapper call writes one audit_log row."""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from briefalpha_api.anonymization import (
    build_aliased_evidence,
    make_alias_context,
)
from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    build_sensitive_entity_dictionary,
)
from briefalpha_api.db.models import AuditLog
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.llm import call_text_llm
from briefalpha_api.llm.prompt_builder import build_request


async def _purge_audit() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(AuditLog))
        await s.commit()


@pytest.mark.asyncio
async def test_text_llm_call_writes_audit_row() -> None:
    await _purge_audit()
    sensitive_dict = build_sensitive_entity_dictionary(universe_tickers=["NVDA"])
    ctx = make_alias_context(
        brief_id="audit-test-1",
        universe_tickers=["NVDA"],
        entity_dictionary=sensitive_dict,
    )
    ae, _ = build_aliased_evidence(
        evidence_id="ev_audit_1",
        title="测试标题",
        excerpt="数据中心营收下调 8% 主因企业端需求趋缓",
        source_tier="news",
        asset_class="us_equity",
        published_at=None,
        ctx=ctx,
    )
    req = build_request(
        scope="stage_a",
        aliased_evidence=[ae, ae.model_copy(update={"evidence_id": "ev_audit_2"})],
    )
    audit_ctx = {"brief_id": "audit-test-1", "audit_mode": "demo"}
    await call_text_llm(req, audit_ctx=audit_ctx, alias_context=ctx)

    async with SessionLocal() as s:
        rows = (await s.execute(select(AuditLog))).scalars().all()
    assert len(rows) >= 1, "expected at least one audit_log row from a stub LLM call"
    matching = [r for r in rows if r.brief_id == "audit-test-1" and r.scope == "stage_a"]
    assert matching, f"no audit row tagged audit-test-1, got: {[r.brief_id for r in rows]}"
    row = matching[0]
    assert row.call_type == "text"
    assert row.audit_mode == "demo"
    # Stub provider returns 2 cited evidence_ids.
    assert isinstance(row.cited_evidence_ids, list)
