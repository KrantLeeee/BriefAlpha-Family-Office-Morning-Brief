"""run_brief: orchestrate the 9 pipeline stages + 3 LLM stages.

Conservative-brief trigger conditions (PRD §5.1.3 / task 10.3):
  1. evidence_pool_full empty
  2. all text-LLM providers fail
  3. accuracy_validator fails 3 times in a row for the same brief

k=3 / cold_start failure ≠ conservative; that goes through
`no_direct_portfolio_link_fallback`.

Public entry points:
  * `run_pipeline(...)` — pure pipeline; takes positions + watchlist,
    returns the structured pipeline output (incl. stage_a/b/c).
  * `run_full_brief(brief_id)` — convenience wrapper used by the router
    + scheduler: reads portfolio from SQLite, runs the pipeline, fetches
    quotes for the portfolio, and emits a frontend-shaped Brief via
    `pipeline.artifact.build_brief_artifact`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from briefalpha_api.anonymization import (
    build_aliased_evidence,
    encrypt_alias_map,
    make_alias_context,
)
from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    build_sensitive_entity_dictionary,
)
from briefalpha_api.audit.source_health_aggregator import aggregate_source_health
from briefalpha_api.db.models import Evidence, ResearchChunk
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.fixtures.brief import get_demo_source_health
from briefalpha_api.ingestion.runner import run_ingestion
from briefalpha_api.llm import call_text_llm, conservative_fallback
from briefalpha_api.llm.prompt_builder import build_request
from briefalpha_api.llm.sensitive_scan import scrub_tree
from briefalpha_api.pipeline import stages
from briefalpha_api.pipeline.artifact import build_brief_artifact
from briefalpha_api.portfolio.models import PortfolioPosition
from briefalpha_api.portfolio.repo import load_positions, load_watchlist
from briefalpha_api.portfolio.universe import build_universe
from briefalpha_api.search.fts import index_evidence

log = logging.getLogger("briefalpha.pipeline")


# ---------------------------------------------------------------------------
# Internal pipeline (LLM stages included)
# ---------------------------------------------------------------------------


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
    ev.extend(await _load_research_evidence(brief_id))
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
        return _conservative_output(brief_id, no_direct_portfolio_link)

    # ─── Anonymization ────────────────────────────────────────────────
    sensitive_dict = build_sensitive_entity_dictionary(
        universe_tickers=[t.ticker for t in universe.tickers]
    )
    ctx = make_alias_context(
        brief_id=brief_id,
        universe_tickers=[t.ticker for t in universe.tickers],
        entity_dictionary=sensitive_dict,
    )
    aliased = []
    quote_segments_by_id: dict[str, list] = {}
    excerpt_aliased_by_id: dict[str, str] = {}
    for e in selected:
        ae, segs = build_aliased_evidence(
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
        quote_segments_by_id[e.evidence_id] = segs
        excerpt_aliased_by_id[e.evidence_id] = ae.excerpt_aliased

    encrypt_alias_map(brief_id, ctx)

    # ─── Build validator inputs once for all three stages ────────────────
    pool_ids = {ae.evidence_id for ae in aliased}
    pool_metadata = _build_pool_metadata(selected)
    cited_excerpts_for_anchor = list(excerpt_aliased_by_id.values())

    # ─── Stage A → B → C ──────────────────────────────────────────────
    audit_ctx = {"brief_id": brief_id, "audit_mode": "demo"}
    aliased_payload = [a.model_dump() for a in aliased]

    stage_a_req = build_request(
        scope="stage_a",
        aliased_evidence=aliased,
        extra_payload={
            "no_direct_portfolio_link": no_direct_portfolio_link,
            "aliased_evidence_json": aliased_payload,
        },
    )
    stage_a_resp = await call_text_llm(
        stage_a_req,
        audit_ctx=audit_ctx,
        alias_context=ctx,
        cited_excerpts_aliased=cited_excerpts_for_anchor,
        accuracy_validate=_make_validator(
            scope="stage_a",
            pool_ids=pool_ids,
            pool_metadata=pool_metadata,
            excerpt_aliased_by_id=excerpt_aliased_by_id,
            quote_segments_by_id=quote_segments_by_id,
            sensitive_dict=sensitive_dict,
            brief_freeze_at_hkt=freeze_at,
        ),
    )

    stage_b_req = build_request(
        scope="stage_b",
        aliased_evidence=aliased,
        extra_payload={
            "no_direct_portfolio_link": no_direct_portfolio_link,
            "aliased_evidence_json": aliased_payload,
        },
    )
    stage_b_resp = await call_text_llm(
        stage_b_req,
        audit_ctx=audit_ctx,
        alias_context=ctx,
        cited_excerpts_aliased=cited_excerpts_for_anchor,
        accuracy_validate=_make_validator(
            scope="stage_b",
            pool_ids=pool_ids,
            pool_metadata=pool_metadata,
            excerpt_aliased_by_id=excerpt_aliased_by_id,
            quote_segments_by_id=quote_segments_by_id,
            sensitive_dict=sensitive_dict,
            brief_freeze_at_hkt=freeze_at,
        ),
    )

    stage_a_struct = stage_a_resp.structured
    stage_b_struct = stage_b_resp.structured
    if stage_a_resp.provider == "conservative" or not (stage_a_struct or {}).get(
        "base_case_headline"
    ):
        stage_a_struct = _fallback_stage_a_from_evidence(selected)
    if stage_b_resp.provider == "conservative" or not (stage_b_struct or {}).get("judgements"):
        stage_b_struct = _fallback_stage_b_from_evidence(
            selected,
            no_direct_portfolio_link=no_direct_portfolio_link,
            last_failure=(stage_b_struct or {}).get("last_failure"),
        )

    # `call_text_llm` reverses aliases in Stage B output so the user-facing
    # artifact can show real names. Before passing those judgements into
    # Stage C, scrub them back to aliases; otherwise Stage C's input scanner
    # correctly rejects real tickers such as "MSFT".
    stage_b_judgements_for_prompt = scrub_tree(
        (stage_b_struct or {}).get("judgements", []),
        dictionary=sensitive_dict,
        ctx=ctx,
    )

    stage_c_req = build_request(
        scope="stage_c",
        aliased_evidence=aliased,
        extra_payload={
            "judgements_json": stage_b_judgements_for_prompt,
            "aliased_evidence_json": aliased_payload,
        },
    )
    # Stage C (playbook_events) currently has no citation rule — citations
    # validator falls through, but we still want the time_window + sensitive
    # checks. Pass the same validator factory for parity.
    stage_c_resp = await call_text_llm(
        stage_c_req,
        audit_ctx=audit_ctx,
        alias_context=ctx,
        cited_excerpts_aliased=cited_excerpts_for_anchor,
        accuracy_validate=_make_validator(
            scope="stage_c",
            pool_ids=pool_ids,
            pool_metadata=pool_metadata,
            excerpt_aliased_by_id=excerpt_aliased_by_id,
            quote_segments_by_id=quote_segments_by_id,
            sensitive_dict=sensitive_dict,
            brief_freeze_at_hkt=freeze_at,
        ),
    )

    conservative = any(
        r.provider == "conservative"
        for r in (stage_a_resp, stage_b_resp, stage_c_resp)
    )

    return {
        "brief_id": brief_id,
        "brief_date_hkt": brief_id,
        "no_direct_portfolio_link": no_direct_portfolio_link,
        "conservative": conservative,
        "stage_a": stage_a_struct,
        "stage_b": stage_b_struct,
        "stage_c": stage_c_resp.structured,
        "evidence_pool_full": [_evidence_dict(e) for e in ev],
        "selected_evidence_for_llm": [_evidence_dict(e) for e in selected],
    }


def _conservative_output(brief_id: str, no_direct_portfolio_link: bool) -> dict[str, Any]:
    return {
        "brief_id": brief_id,
        "brief_date_hkt": brief_id,
        "no_direct_portfolio_link": no_direct_portfolio_link,
        "conservative": True,
        "stage_a": conservative_fallback("stage_a").structured,
        "stage_b": {"judgements": []},
        "stage_c": {"playbook_events": []},
        "evidence_pool_full": [],
        "selected_evidence_for_llm": [],
    }


def _fallback_stage_a_from_evidence(selected: list[stages.Evidence]) -> dict[str, Any]:
    cited = [e.evidence_id for e in selected[:2]]
    top = selected[0] if selected else None
    headline = "保守模式：等待更多可验证证据"
    summary = "LLM 输出未通过校验，系统基于已筛选证据生成保守摘要，建议人工复核后使用。"
    if top is not None:
        headline = f"保守模式：{_truncate(top.title, 42)}"
        summary = _truncate(top.excerpt or top.title, 180)
    return {
        "base_case_headline": headline,
        "summary": summary,
        "cited_evidence_ids": cited,
    }


def _fallback_stage_b_from_evidence(
    selected: list[stages.Evidence],
    *,
    no_direct_portfolio_link: bool,
    last_failure: str | None = None,
) -> dict[str, Any]:
    """Conservative Stage B output when the LLM call collapses.

    Anchors one judgement per available source tier (news / official /
    research / market) so the UI surfaces multi-source evidence even when
    the model is offline. The original implementation cited `selected[:2]`,
    which under live data was always two yfinance market quotes (the
    highest-scoring tier) and hid every news/official/research item that
    the pipeline had spent work fetching and selecting.

    Each fallback judgement carries an explicit `review` dict whose `note`
    field tells the user *why* the LLM was rejected and *which* evidence
    we used to anchor the placeholder. Without this, the review modal
    showed an empty "数据缺口或质量问题" with no actionable detail.
    """
    if not selected:
        return {"judgements": []}

    by_tier: dict[str, list[stages.Evidence]] = {}
    for ev in selected:
        by_tier.setdefault(ev.source_tier, []).append(ev)

    # Tier order favors human-readable narrative tiers over price ticks so
    # the first fallback judgement is news/official rather than yfinance.
    tier_priority = ["news", "official", "research", "market"]
    primaries: list[stages.Evidence] = []
    for tier in tier_priority:
        bucket = by_tier.get(tier)
        if bucket:
            primaries.append(bucket[0])
        if len(primaries) >= 3:
            break
    if not primaries:
        primaries = [selected[0]]

    failure_summary = _summarize_failure(last_failure)
    review_reason = _failure_to_review_reason(last_failure)

    judgements: list[dict[str, Any]] = []
    for rank, primary in enumerate(primaries, start=1):
        # Each judgement must cite ≥ 2 evidences (Stage B citation rule).
        # Prefer a supporting evidence from a *different* tier than the
        # primary so the cited card on the UI shows mixed sources.
        supporting = next(
            (e for e in selected if e.evidence_id != primary.evidence_id and e.source_tier != primary.source_tier),
            None,
        )
        if supporting is None:
            supporting = next(
                (e for e in selected if e.evidence_id != primary.evidence_id),
                primary,
            )
        cited = list(dict.fromkeys([primary.evidence_id, supporting.evidence_id]))
        tickers = ", ".join(primary.detected_tickers[:3]) or "相关资产"
        cited_titles = " / ".join(
            f"{e.source_name}：{_truncate(e.title, 30)}"
            for e in (primary, supporting)
            if e.evidence_id in cited
        )
        note = (
            f"AI 未生成此条研判（{failure_summary}）。"
            f"系统以最高分 {primary.source_tier} evidence 拼出占位条目供你定位"
            f"原始来源（{cited_titles}）；这条本身不是 AI 推理结果。"
        )
        judgements.append(
            {
                "rank": rank,
                "level": "watch",
                "title": f"保守复核：{_truncate(primary.title, 46)}",
                "reasoning_chain": {
                    "observed": _truncate(primary.excerpt or primary.title, 160),
                    "portfolio_exposure": (
                        "仅展示资产类别层面的关联，未直接披露组合权重。"
                        if no_direct_portfolio_link
                        else f"相关标的：{tickers}"
                    ),
                    "inference": "LLM 输出未通过数字或引用校验，当前结论按保守模式处理。",
                    "conclusion": "进入关注列表，待数据源恢复或人工复核后再提升置信度。",
                },
                "cited_evidence_ids": cited,
                "no_direct_portfolio_link": no_direct_portfolio_link,
                "requires_review": True,
                "review": {
                    "reason": review_reason,
                    "note": note,
                    "status": "open",
                    "reviewed_at": None,
                    "kind": "fallback",
                },
            }
        )

    return {"judgements": judgements}


def _summarize_failure(last_failure: str | None) -> str:
    """Translate a wrapper failure code into a short human-readable phrase
    for the review note. Keep it short — the modal already shows the
    `reason` chip; this is the supporting one-liner."""
    if not last_failure:
        return "Stage B 全部 retry 失败"
    if last_failure.startswith("accuracy:numbers"):
        return "Stage B 输出含 cited evidence 中找不到的带单位数字，3 次 retry 都被拒"
    if last_failure.startswith("accuracy:citations"):
        return "Stage B 输出引用了不在 evidence pool 的 id"
    if last_failure.startswith("accuracy:polarity"):
        return "Stage B 输出方向与 excerpt 矛盾"
    if last_failure.startswith("accuracy:time_window"):
        return "Stage B 引用了时间窗口外的 evidence"
    if last_failure.startswith("accuracy:quote_span"):
        return "Stage B 输出 quote_span 校验失败"
    if last_failure.startswith("sensitive_output"):
        return "Stage B 输出触发敏感词扫描"
    if last_failure.startswith("provider_error"):
        return "Stage B LLM 提供方调用失败"
    return f"Stage B 失败：{last_failure[:80]}"


def _failure_to_review_reason(last_failure: str | None) -> str:
    """Pick the closest existing reason taxonomy slot for the failure.
    The frontend's `ReviewMeta.reason` enum is fixed; we map onto it
    rather than introducing a new value (which would require coordinated
    UI label changes)."""
    if not last_failure:
        return "data_gap"
    if last_failure.startswith("accuracy:numbers") or last_failure.startswith("accuracy:polarity"):
        # Closest semantic match — the LLM and the source disagreed on
        # quantitative facts.
        return "source_conflict"
    if last_failure.startswith("accuracy:time_window"):
        return "threshold_breach"
    return "data_gap"


def _truncate(value: str, max_chars: int) -> str:
    text = " ".join((value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _build_pool_metadata(selected: list[stages.Evidence]) -> dict[str, Any]:
    """Build the {evidence_id: EvidencePoolEntry} map the validator wants."""
    from briefalpha_api.validator.runner import EvidencePoolEntry

    return {
        e.evidence_id: EvidencePoolEntry(
            source_tier=e.source_tier,
            asset_class=e.asset_class,
            published_at=e.published_at,
        )
        for e in selected
    }


def _make_validator(
    *,
    scope: str,
    pool_ids: set[str],
    pool_metadata: dict[str, Any],
    excerpt_aliased_by_id: dict[str, str],
    quote_segments_by_id: dict[str, list],
    sensitive_dict: Any,
    brief_freeze_at_hkt: Any,
):
    """Return an `accuracy_validate` callback wired with this stage's context.

    The wrapper invokes this on every provider response. Failures cause one
    retry per the wrapper's `MAX_RETRY_TEXT=3` budget; if all attempts
    fail the wrapper returns `conservative_fallback`. This is the runtime
    safety net the spec calls for in design.md §4.4 (citations / quote_span
    / numbers / polarity / time_window / sensitive output all enforced
    at production time, not just measured offline by the golden runner).
    """
    from briefalpha_api.validator.runner import validate_response

    async def _validate(resp: Any) -> tuple[bool, str | None]:
        structured = resp.structured or {}

        # Pick the answer text we feed `validate_numbers` /
        # `validate_polarity` from the structured response. Each stage's
        # template has a different primary text field; we concatenate the
        # ones that exist so number / polarity hallucinations anywhere in
        # the visible output are caught.
        answer_chunks: list[str] = []
        for k in ("base_case_headline", "summary"):
            v = structured.get(k)
            if isinstance(v, str):
                answer_chunks.append(v)
        for j in structured.get("judgements", []) or []:
            for k in ("title", "evidence_summary", "reasoning_chain"):
                v = j.get(k)
                if isinstance(v, str):
                    answer_chunks.append(v)
                elif isinstance(v, dict):
                    answer_chunks.extend(str(x) for x in v.values() if isinstance(x, str))
        for ev in structured.get("playbook_events", []) or []:
            for k in ("label", "detail"):
                v = ev.get(k)
                if isinstance(v, str):
                    answer_chunks.append(v)
        answer_text = "\n".join(answer_chunks)

        # Citation context: only quote-span segments belonging to cited
        # evidence inform the quote_span check (any cited evidence works
        # for the validator since we project span coords forward per excerpt).
        cited_ids: list[str] = list(structured.get("cited_evidence_ids", []))
        if scope == "stage_b":
            for j in structured.get("judgements", []) or []:
                cited_ids.extend(j.get("cited_evidence_ids", []) or [])
        excerpt_text = "\n".join(
            excerpt_aliased_by_id.get(cid, "")
            for cid in cited_ids
            if cid in excerpt_aliased_by_id
        ) or "\n".join(excerpt_aliased_by_id.values())

        # News tier expansion: when the LLM cites at least one news evidence,
        # treat the entire selected news pool as supporting context for the
        # numbers check. News excerpts are inherently qualitative — a Stage B
        # judgement that anchors on a news headline shouldn't be punished for
        # mentioning a number that lives in a non-cited news item from the
        # same brief. This matters because the original strict rule pushed
        # the LLM into self-censoring news entirely (see audit log 2026-04-27),
        # leaving every fallback judgement citing only yfinance + research.
        # Non-news cites stay as strict as before — the expansion only adds
        # context, never removes it.
        cited_set = set(cited_ids)
        news_ids_in_pool = {
            eid
            for eid, entry in (pool_metadata or {}).items()
            if getattr(entry, "source_tier", None) == "news"
        }
        if cited_set & news_ids_in_pool:
            extra_news = "\n".join(
                excerpt_aliased_by_id[eid]
                for eid in news_ids_in_pool - cited_set
                if eid in excerpt_aliased_by_id
            )
            if extra_news:
                excerpt_text = excerpt_text + "\n" + extra_news

        result = validate_response(
            structured=structured,
            pool_ids=pool_ids,
            scope=scope,
            quote_span_segments=None,
            excerpt_text=excerpt_text,
            answer_text=answer_text,
            quote_span_aliased=None,
            sensitive_dict=sensitive_dict,
            pool_metadata=pool_metadata,
            brief_freeze_at_hkt=brief_freeze_at_hkt,
        )
        return result.ok, result.reason

    return _validate


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
        "fetched_at": ev.fetched_at.isoformat() if ev.fetched_at else None,
        "quote_span": ev.quote_span,
        "source_reliability": ev.source_reliability,
        "base_score": ev.base_score,
        "final_impact_score": ev.final_impact_score,
        "score_breakdown": ev.score_breakdown,
        "selected_for_llm": ev.selected_for_llm,
        "conflict": ev.conflict,
        "requires_review": ev.requires_review,
        "supplementary_sources": ev.supplementary_sources,
        "raw_source_url": ev.raw_source_url,
    }


# ---------------------------------------------------------------------------
# Public top-level entry
# ---------------------------------------------------------------------------


async def run_full_brief(
    brief_id: str,
    *,
    user_id: str = "demo",
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Read portfolio + watchlist from SQLite, run the full pipeline, and
    return a frontend-shaped Brief artifact.

    This is the function the router and the scheduler invoke. Errors
    propagate so callers can decide whether to fall back to the fixture.
    """
    own_session = session is None
    if session is None:
        session = SessionLocal()
    try:
        positions = await load_positions(session, user_id=user_id)
        watchlist = await load_watchlist(session, user_id=user_id)
    finally:
        if own_session:
            await session.close()

    if not positions:
        log.warning("run_full_brief(%s): no portfolio rows for %s", brief_id, user_id)

    pipeline_output = await run_pipeline(
        brief_id=brief_id, positions=positions, watchlist=watchlist
    )
    await _persist_evidence_pool(brief_id, pipeline_output.get("evidence_pool_full", []))

    # Quotes — best effort. yfinance is rate-limited; failures yield empty
    # dict and the artifact builder falls back to "0.0%" / "flat" trend.
    quotes = await _fetch_quotes([p.ticker for p in positions])

    # Source health: read the live aggregator (driven by ingestion runs +
    # the every-5-min cron). Falls back to the demo fixture only when the
    # SourceHealthHistory table is still empty (first boot, no ingestion
    # has run yet).
    try:
        source_health = await aggregate_source_health()
        if not source_health.get("rows"):
            source_health = get_demo_source_health()
    except Exception as exc:  # noqa: BLE001
        log.warning("source_health aggregation failed (%s); using fixture", exc)
        source_health = get_demo_source_health()

    artifact = build_brief_artifact(
        pipeline_output=pipeline_output,
        portfolio_positions=[
            {"ticker": p.ticker, "weight": p.weight, "asset_class": p.asset_class}
            for p in positions
        ],
        watchlist=watchlist,
        source_health=source_health,
        quotes=quotes,
    )
    return artifact


async def _persist_evidence_pool(brief_id: str, evidence_pool: list[dict[str, Any]]) -> None:
    """Persist the generated evidence pool for QA and the evidence trail drawer.

    The brief artifact is cached separately for fast rendering, but QA and
    `/api/evidence/trail` intentionally read SQLite/FTS. Without this bridge,
    the UI can say "96 条原文" while the drawer and QA see an empty database.
    """
    async with SessionLocal() as session:
        await session.execute(
            delete(Evidence)
            .where(Evidence.brief_id == brief_id)
            .where(Evidence.source_tier != "research")
        )
        await session.execute(
            text(
                "DELETE FROM evidence_fts "
                "WHERE brief_id = :brief_id AND source_tier != 'research'"
            ),
            {"brief_id": brief_id},
        )
        for ev in evidence_pool:
            if ev.get("source_tier") == "research":
                existing = await session.get(Evidence, ev["evidence_id"])
                if existing is not None:
                    existing.base_score = float(ev.get("base_score") or existing.base_score or 0.0)
                    existing.final_impact_score = float(
                        ev.get("final_impact_score") or existing.final_impact_score or 0.0
                    )
                    existing.selected_for_llm = bool(ev.get("selected_for_llm"))
                    existing.conflict = bool(ev.get("conflict"))
                    existing.requires_review = bool(ev.get("requires_review"))
                    existing.exposure_bucket = ev.get("exposure_bucket") or existing.exposure_bucket
                    existing.score_breakdown = dict(
                        ev.get("score_breakdown") or existing.score_breakdown or {}
                    )
                continue
            published_at = _parse_iso_datetime(ev.get("published_at"))
            fetched_at = _parse_iso_datetime(ev.get("fetched_at")) or datetime.now(
                timezone.utc
            )
            score_breakdown = dict(ev.get("score_breakdown") or {})
            if ev.get("source_name"):
                score_breakdown["source_name"] = ev.get("source_name")
            row = Evidence(
                evidence_id=ev["evidence_id"],
                brief_id=brief_id,
                source_tier=ev.get("source_tier") or "news",
                source_reliability=float(ev.get("source_reliability") or 0.5),
                title=ev.get("title") or "",
                excerpt=ev.get("excerpt") or "",
                quote_span=ev.get("quote_span"),
                detected_tickers=list(ev.get("detected_tickers") or []),
                chunk_type=ev.get("chunk_type"),
                asset_class=ev.get("asset_class"),
                exposure_bucket=ev.get("exposure_bucket"),
                published_at=published_at,
                fetched_at=fetched_at,
                base_score=float(ev.get("base_score") or 0.0),
                final_impact_score=float(ev.get("final_impact_score") or 0.0),
                score_breakdown=score_breakdown,
                selected_for_llm=bool(ev.get("selected_for_llm")),
                conflict=bool(ev.get("conflict")),
                requires_review=bool(ev.get("requires_review")),
                supplementary_sources=list(ev.get("supplementary_sources") or []),
                raw_source_url=ev.get("raw_source_url"),
            )
            session.add(row)
            await index_evidence(
                session,
                evidence_id=row.evidence_id,
                brief_id=brief_id,
                title=row.title,
                excerpt=row.excerpt,
                detected_tickers=row.detected_tickers,
                chunk_type=row.chunk_type,
                source_tier=row.source_tier,
            )
        await session.commit()


async def _load_research_evidence(brief_id: str) -> list[stages.Evidence]:
    """Bring already parsed research chunks into the next brief run.

    Upload parsing persists research rows before the user asks to regenerate
    the brief. The pipeline then treats those rows as first-class evidence
    instead of relying on a side table that the generation pass cannot see.
    """
    await _backfill_research_evidence_rows(brief_id)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Evidence)
                .where(Evidence.brief_id == brief_id)
                .where(Evidence.source_tier == "research")
            )
        ).scalars().all()
    return [
        stages.Evidence(
            evidence_id=row.evidence_id,
            source_tier=row.source_tier,
            source_name=(row.score_breakdown or {}).get("source_name") or "research",
            source_reliability=row.source_reliability,
            title=row.title,
            excerpt=row.excerpt,
            quote_span=None,
            detected_tickers=list(row.detected_tickers or []),
            chunk_type=row.chunk_type,
            asset_class=row.asset_class,
            exposure_bucket=row.exposure_bucket,
            published_at=row.published_at,
            fetched_at=row.fetched_at,
            base_score=row.base_score,
            final_impact_score=row.final_impact_score,
            score_breakdown=dict(row.score_breakdown or {}),
            selected_for_llm=False,
            conflict=bool(row.conflict),
            requires_review=bool(row.requires_review),
            supplementary_sources=list(row.supplementary_sources or []),
            raw_source_url=row.raw_source_url,
        )
        for row in rows
    ]


async def _backfill_research_evidence_rows(brief_id: str) -> int:
    """Repair parsed research chunks that predate evidence persistence.

    Some local/dev runs can have `research_chunks` rows with an `evidence_id`
    but no matching `evidence` row (for example after code changed between
    parsing and regenerating). Without this bridge, the parse report says OK
    while the brief pipeline never sees the uploaded research.
    """
    written = 0
    async with SessionLocal() as session:
        chunks = (
            await session.execute(
                select(ResearchChunk).where(ResearchChunk.brief_id == brief_id)
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for ch in chunks:
            if not ch.evidence_id:
                continue
            existing = await session.get(Evidence, ch.evidence_id)
            if existing is not None:
                continue
            title = ch.heading or f"Research upload · p{ch.page}"
            row = Evidence(
                evidence_id=ch.evidence_id,
                brief_id=brief_id,
                source_tier="research",
                source_reliability=0.5,
                title=title,
                excerpt=ch.content,
                quote_span=None,
                detected_tickers=list(ch.detected_tickers or []),
                chunk_type=ch.chunk_type,
                asset_class=None,
                exposure_bucket=None,
                published_at=now,
                fetched_at=now,
                base_score=0.4,
                final_impact_score=0.4,
                score_breakdown={"source_name": "research", "reliability": 0.5},
                selected_for_llm=False,
                conflict=False,
                requires_review=False,
                supplementary_sources=[
                    {"source_name": "research", "url": f"research://{ch.file_id}"}
                ],
                raw_source_url=f"research://{ch.file_id}#p{ch.page}",
            )
            session.add(row)
            await index_evidence(
                session,
                evidence_id=row.evidence_id,
                brief_id=brief_id,
                title=row.title,
                excerpt=row.excerpt,
                detected_tickers=row.detected_tickers,
                chunk_type=row.chunk_type,
                source_tier=row.source_tier,
            )
            written += 1
        if written:
            await session.commit()
    return written


def _parse_iso_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _fetch_quotes(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch overnight change% for each ticker (best-effort, never raises)."""
    if not tickers:
        return {}
    try:
        import asyncio

        import yfinance  # type: ignore[import-untyped]

        def _quote_one(ticker: str) -> dict[str, Any] | None:
            try:
                tk = yfinance.Ticker(ticker)
                fast = tk.fast_info
                last = float(getattr(fast, "last_price", 0) or 0)
                prev = float(getattr(fast, "previous_close", 0) or 0)
                if prev <= 0 or last <= 0:
                    return None
                pct = (last - prev) / prev * 100.0
                return {"last": last, "previous_close": prev, "change_pct": pct}
            except Exception:  # noqa: BLE001
                return None

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None, lambda: {t: _quote_one(t) for t in tickers}
        )
        return {t: q for t, q in results.items() if q is not None}
    except Exception as exc:  # noqa: BLE001
        log.warning("yfinance quote batch failed: %s", exc)
        return {}
