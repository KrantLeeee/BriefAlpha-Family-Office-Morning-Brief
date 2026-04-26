"""QA service — orchestrates the safe QA flow per design.md §3 / task 13.3.

Sequence:
  1. Decrypt the brief's alias_map (else `brief_expired`).
  2. Apply alias replacement to the user question.
  3. FTS search in the requested scope (judgement / evidence / global).
  4. Hydrate matching `Evidence` rows from SQLite, then run them through
     anonymization → `AliasedEvidence` (FTS rows are NOT allowed to flow
     directly into the prompt — wrapper input scan would catch it anyway).
  5. Call `call_text_llm(qa_local|qa_global)` with the wrapped accuracy
     validator.
  6. Reverse-alias the answer using cited evidence anchors.
  7. Return a stable response shape that matches the frontend QaResponse.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from briefalpha_api.anonymization import (
    build_aliased_evidence,
    decrypt_alias_map,
)
from briefalpha_api.anonymization.replace import replace_in_text
from briefalpha_api.anonymization.reverse import reverse_alias
from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    build_sensitive_entity_dictionary,
)
from briefalpha_api.cache import get_json, qa_context_key, set_json
from briefalpha_api.db.models import Evidence
from briefalpha_api.llm import call_text_llm
from briefalpha_api.llm.prompt_builder import build_request
from briefalpha_api.search import search

log = logging.getLogger("briefalpha.qa")

QA_CONTEXT_TTL_SECONDS = 6 * 60 * 60
QA_HISTORY_TURNS = 3
SEARCH_LIMIT = 8

Scope = Literal["judgement", "evidence", "global"]


@dataclass
class QaServiceResult:
    answer: str
    cited_evidence_ids: list[str] = field(default_factory=list)
    citations: list[dict[str, str]] = field(default_factory=list)
    insufficient_evidence: bool = False
    validation_passed: bool = True
    failure_reason: str | None = None


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run_qa(
    session: AsyncSession,
    *,
    brief_id: str,
    scope: Scope,
    scope_target_id: str | None,
    question: str,
) -> QaServiceResult:
    if not question.strip():
        return QaServiceResult(
            answer="问题不能为空。",
            insufficient_evidence=True,
            validation_passed=False,
            failure_reason="empty_question",
        )

    # Step 1: alias context (alias_map ciphertext on disk).
    try:
        ctx = decrypt_alias_map(brief_id)
    except FileNotFoundError:
        return QaServiceResult(
            answer="该 brief 的别名映射已过期（每日 16:00 HKT 销毁），请基于今日 brief 重新追问。",
            insufficient_evidence=False,
            validation_passed=False,
            failure_reason="brief_expired",
        )

    universe_tickers = list(ctx.alias_to_ticker.values())
    sensitive_dict = build_sensitive_entity_dictionary(universe_tickers=universe_tickers)
    if ctx.entity_dictionary is None:
        ctx.entity_dictionary = sensitive_dict

    # Step 2a: aliased copy of the question for the LLM payload (defensive
    # — if the user typed a real ticker, it must NOT cross the wrapper
    # boundary in cleartext).
    aliased_question, _segs = replace_in_text(question, ctx, field="user_question")

    # Step 2b: the FTS index stores raw (unaliased) evidence by design,
    # so we MUST search with the original terms. Aliasing the question
    # before search would silently cause "no hits" for any ticker query.
    hits = await search(
        session,
        brief_id=brief_id,
        query=_search_query_from(question),
        scope=scope,
        evidence_id=scope_target_id if scope == "evidence" else None,
        limit=SEARCH_LIMIT,
    )
    if not hits:
        return QaServiceResult(
            answer="evidence 不足以回答该问题（基于今日 brief 的可引用范围）。",
            insufficient_evidence=True,
            validation_passed=True,
            cited_evidence_ids=[],
        )

    hit_ids = [h.evidence_id for h in hits]
    ev_rows = (
        await session.execute(select(Evidence).where(Evidence.evidence_id.in_(hit_ids)))
    ).scalars().all()
    if not ev_rows:
        return QaServiceResult(
            answer="evidence 不足以回答该问题（FTS 命中但 evidence 表已清理）。",
            insufficient_evidence=True,
            validation_passed=True,
        )

    # Step 4: anonymize hydrated evidence (re-alias, never use raw FTS rows).
    aliased_evidences = []
    excerpt_aliased_by_id: dict[str, str] = {}
    for ev in ev_rows:
        ae, _segs = build_aliased_evidence(
            evidence_id=ev.evidence_id,
            title=ev.title,
            excerpt=ev.excerpt,
            source_tier=ev.source_tier,  # type: ignore[arg-type]
            asset_class=ev.asset_class,
            published_at=ev.published_at,
            ctx=ctx,
            quote_span_original=(
                tuple(ev.quote_span.values()) if isinstance(ev.quote_span, dict) and len(ev.quote_span) == 2 else None
            ),
        )
        aliased_evidences.append(ae)
        excerpt_aliased_by_id[ev.evidence_id] = ae.excerpt_aliased

    pool_ids = {ae.evidence_id for ae in aliased_evidences}

    # Step 5: build prompt + call wrapper with accuracy validator.
    template_scope = "qa_global" if scope == "global" else "qa_local"
    history = await _load_qa_history(brief_id, scope, scope_target_id)
    extra_payload: dict[str, Any] = {
        "scope": scope,
        "scope_target_id": scope_target_id,
        "user_question_aliased": aliased_question,
        "aliased_evidence_json": [ae.model_dump() for ae in aliased_evidences],
        "qa_history_json": history,
    }
    req = build_request(
        scope=template_scope,  # type: ignore[arg-type]
        aliased_evidence=aliased_evidences,
        extra_payload=extra_payload,
        max_tokens=600,
    )

    # Pre-build the time-window pool_metadata once.
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _ZI

    from briefalpha_api.validator.runner import EvidencePoolEntry

    pool_metadata = {
        ev.evidence_id: EvidencePoolEntry(
            source_tier=ev.source_tier,
            asset_class=ev.asset_class,
            published_at=ev.published_at,
        )
        for ev in ev_rows
    }
    # Brief freeze time: read 07:55 HKT of brief_id (the published cron
    # convention). If brief_id isn't a date, fall back to "now".
    try:
        brief_freeze_at_hkt = _dt.strptime(brief_id, "%Y-%m-%d").replace(
            hour=7, minute=55, tzinfo=_ZI("Asia/Hong_Kong")
        )
    except ValueError:
        brief_freeze_at_hkt = _dt.now(tz=_ZI("Asia/Hong_Kong"))

    async def _validate(resp: Any) -> tuple[bool, str | None]:
        from briefalpha_api.validator.runner import validate_response

        # IMPORTANT: feed the answer text (not the JSON wrapper) — digits
        # inside `evidence_id` values would otherwise look like hallucinated
        # numbers to validate_numbers.
        structured = resp.structured or {}
        answer_only = structured.get("answer") or ""
        result = validate_response(
            structured=structured,
            pool_ids=pool_ids,
            scope=template_scope,
            quote_span_segments=None,
            excerpt_text="\n".join(excerpt_aliased_by_id.values()),
            answer_text=answer_only,
            quote_span_aliased=None,
            sensitive_dict=sensitive_dict,
            pool_metadata=pool_metadata,
            brief_freeze_at_hkt=brief_freeze_at_hkt,
        )
        return result.ok, result.reason

    audit_ctx = {"brief_id": brief_id, "audit_mode": "demo", "qa_scope": scope}
    cited_excerpts_for_anchor = list(excerpt_aliased_by_id.values())
    resp = await call_text_llm(
        req,
        audit_ctx=audit_ctx,
        alias_context=ctx,
        cited_excerpts_aliased=cited_excerpts_for_anchor,
        accuracy_validate=_validate,
    )

    structured = resp.structured or {}
    answer_text = resp.text or structured.get("answer", "")
    cited = list(structured.get("cited_evidence_ids", []))
    insufficient = bool(structured.get("insufficient_evidence"))

    if resp.provider == "conservative":
        return QaServiceResult(
            answer="当前无法生成可信回答（连续验证失败或 provider 不可用），请稍后再试。",
            insufficient_evidence=False,
            validation_passed=False,
            failure_reason="conservative_fallback",
        )

    # Step 6: safe reverse alias on the answer text (already done inside
    # wrapper if alias_context+cited_excerpts supplied; we keep an explicit
    # second pass to also hand the caller `unsafe_generated_aliases` count).
    reversed_result = reverse_alias(
        answer_text,
        ctx,
        cited_evidence_excerpts_aliased=cited_excerpts_for_anchor,
    )

    citations = []
    for idx, eid in enumerate(cited[:5], start=1):
        circled = "①②③④⑤⑥⑦⑧⑨⑩"
        citations.append(
            {
                "evidence_id": eid,
                "label": f"{circled[idx - 1] if idx <= len(circled) else f'({idx})'} {_label_for_evidence(ev_rows, eid)}",
            }
        )

    # Step 7: persist short rolling QA context.
    await _push_qa_history(
        brief_id, scope, scope_target_id, question=question, answer=reversed_result.text
    )

    return QaServiceResult(
        answer=reversed_result.text,
        cited_evidence_ids=cited,
        citations=citations,
        insufficient_evidence=insufficient,
        validation_passed=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _search_query_from(question: str) -> str:
    """Very lightweight tokenizer — keep alphanumerics + Han chars, drop the
    rest. FTS5 unicode61 tokenizer takes care of the heavy lifting."""
    import re

    cleaned = re.sub(r"[^\w一-鿿\s]", " ", question)
    return cleaned.strip()


def _label_for_evidence(ev_rows: list[Evidence], evidence_id: str) -> str:
    for ev in ev_rows:
        if ev.evidence_id == evidence_id:
            pub = ev.published_at.strftime("%m-%d %H:%M") if ev.published_at else ""
            return " · ".join(filter(None, [ev.source_name if hasattr(ev, "source_name") else ev.source_tier, pub]))
    return evidence_id


async def _load_qa_history(
    brief_id: str, scope: str, target_id: str | None
) -> list[dict[str, str]]:
    key = qa_context_key(brief_id, scope, target_id)
    history = await get_json(key)
    if not isinstance(history, list):
        return []
    return history[-QA_HISTORY_TURNS:]


async def _push_qa_history(
    brief_id: str, scope: str, target_id: str | None, *, question: str, answer: str
) -> None:
    key = qa_context_key(brief_id, scope, target_id)
    history = await get_json(key) or []
    if not isinstance(history, list):
        history = []
    history.append({"q": question, "a": answer})
    await set_json(key, history[-QA_HISTORY_TURNS:], ttl_seconds=QA_CONTEXT_TTL_SECONDS)
