"""LLM wrapper — the only allowed boundary to provider SDKs.

Per design.md §4.4:
1. validate request schema (whitelist),
2. input sensitive scan,
3. audit pre-hook,
4. provider call (with retries),
5. output sensitive scan,
6. accuracy_validator,
7. audit post-hook,
8. safe reverse alias.

Conservative fallback fires when:
- evidence_pool_full is empty (handled before calling wrapper), OR
- all providers fail, OR
- accuracy_validator fails 3 times in a row for the same brief.

k=3 / cold_start failure MUST NOT trigger conservative — it goes through
`pipeline.no_direct_portfolio_link_fallback` instead.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from briefalpha_api.anonymization.alias import AliasContext
from briefalpha_api.anonymization.reverse import reverse_alias
from briefalpha_api.audit import AuditRecord, record_audit_async
from briefalpha_api.llm import providers
from briefalpha_api.llm.schema import LlmRequest, LlmResponse, ProviderError
from briefalpha_api.llm.sensitive_scan import (
    scan_input_for_real_tickers,
    scan_output_for_sensitive_terms,
    scrub_output,
)
from briefalpha_api.settings import get_settings

log = logging.getLogger("briefalpha.llm")

MAX_RETRY_TEXT = 3
MAX_RETRY_QA = 1
MAX_RETRY_VISION = 1


def _request_hash(req: LlmRequest) -> str:
    body = req.model_dump_json(exclude={"aliased_evidence"})
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _response_hash(resp: LlmResponse) -> str:
    return hashlib.sha256((resp.text or "").encode("utf-8")).hexdigest()


def _retry_budget(scope: str) -> int:
    if scope.startswith("qa"):
        return MAX_RETRY_QA
    if scope == "vision":
        return MAX_RETRY_VISION
    return MAX_RETRY_TEXT


def _audit_pre(req: LlmRequest, *, audit_ctx: dict) -> dict:
    """Capture pre-call metadata; the actual DB write happens in
    `_audit_post` so we have one row per call (success or failure)."""
    return {
        "request_hash": _request_hash(req),
        "scope": req.scope,
        "call_type": req.call_type,
        "template_version": req.template_version,
        "audit_mode": audit_ctx.get("audit_mode", "demo"),
        "brief_id": audit_ctx.get("brief_id"),
    }


async def _audit_post(
    pre: dict,
    resp: LlmResponse | None,
    *,
    failure_state: str | None,
    accuracy_validation_passed: bool | None,
) -> None:
    rec = AuditRecord(
        request_hash=pre["request_hash"],
        response_hash=_response_hash(resp) if resp else None,
        scope=pre["scope"],
        cited_evidence_ids=list(resp.cited_evidence_ids) if resp else [],
        accuracy_validation_passed=accuracy_validation_passed,
        call_type=pre["call_type"],
        provider=resp.provider if resp else None,
        model=resp.model if resp else None,
        template_version=pre["template_version"],
        latency_ms=resp.latency_ms if resp else None,
        failure_state=failure_state,
        audit_mode=pre["audit_mode"],
        brief_id=pre["brief_id"],
    )
    await record_audit_async(rec)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


async def call_text_llm(
    req: LlmRequest,
    *,
    audit_ctx: dict[str, Any],
    alias_context: AliasContext | None = None,
    cited_excerpts_aliased: list[str] | None = None,
    accuracy_validate: Any | None = None,
) -> LlmResponse:
    LlmRequest.model_validate(req.model_dump())
    if alias_context is not None:
        # Input sensitive scan: real tickers MUST NOT appear in the request.
        scan_input_for_real_tickers(req.model_dump(), alias_context)
    pre = _audit_pre(req, audit_ctx=audit_ctx)

    settings = get_settings()
    provider = settings.llm_provider

    last_resp: LlmResponse | None = None
    failure: str | None = None
    last_validation: bool | None = None
    for attempt in range(_retry_budget(req.scope)):
        try:
            resp = await providers.call_text_provider(req, provider=provider)
        except ProviderError as exc:
            failure = f"provider_error:{exc}"
            log.warning("provider error attempt %s: %s", attempt, exc)
            continue

        # Output sensitive scan
        if alias_context and resp.text:
            report = scan_output_for_sensitive_terms(
                resp.text, dictionary=alias_context.entity_dictionary or _empty_dict()
            )
            if report.matched_terms:
                # One retry, then scrub
                if attempt + 1 < _retry_budget(req.scope):
                    failure = "sensitive_output:retry"
                    continue
                resp = resp.model_copy(
                    update={
                        "text": scrub_output(
                            resp.text,
                            dictionary=alias_context.entity_dictionary or _empty_dict(),
                            ctx=alias_context,
                        )
                    }
                )

        # Accuracy validation (caller-supplied)
        if accuracy_validate is not None and resp.structured is not None:
            ok, reason = await accuracy_validate(resp)
            last_validation = bool(ok)
            if not ok:
                failure = f"accuracy:{reason}"
                if attempt + 1 < _retry_budget(req.scope):
                    continue
                # All retries exhausted — fall through to conservative
                last_resp = resp
                break

        # Safe reverse alias on any free-text fields (text + structured.answer)
        if alias_context and resp.text:
            r = reverse_alias(
                resp.text,
                alias_context,
                cited_evidence_excerpts_aliased=cited_excerpts_aliased or [],
            )
            resp = resp.model_copy(update={"text": r.text})

        await _audit_post(
            pre,
            resp,
            failure_state=None,
            accuracy_validation_passed=last_validation if accuracy_validate is not None else None,
        )
        return resp

    await _audit_post(
        pre,
        last_resp,
        failure_state=failure or "all_attempts_failed",
        accuracy_validation_passed=last_validation if accuracy_validate is not None else None,
    )
    return conservative_fallback(req.scope)


async def call_vision_llm(
    req: LlmRequest,
    *,
    audit_ctx: dict[str, Any],
) -> LlmResponse:
    """Vision wrapper. Identity-stripping happens here (caller MUST NOT pass
    user_id / session_id / portfolio_id via `audit_ctx.identity_fields`)."""
    if any(k in audit_ctx for k in ("user_id", "session_id", "account_id", "portfolio_id")):
        # Defensive: caller forgot to strip — strip here too.
        audit_ctx = {
            k: v
            for k, v in audit_ctx.items()
            if k not in {"user_id", "session_id", "account_id", "portfolio_id"}
        }
    pre = _audit_pre(req, audit_ctx=audit_ctx)
    try:
        resp = await providers.call_vision_provider(req, provider="openai")
    except ProviderError as exc:
        await _audit_post(
            pre,
            None,
            failure_state=f"vision_provider_error:{exc}",
            accuracy_validation_passed=None,
        )
        return LlmResponse(
            text="caption_unavailable",
            provider="stub",
            model="stub-vision",
            template_version=req.template_version,
            latency_ms=0,
            finish_reason="provider_error",
        )
    await _audit_post(pre, resp, failure_state=None, accuracy_validation_passed=None)
    return resp


async def call_embedding(text: str) -> list[float]:
    settings = get_settings()
    if not settings.third_party_embedding_enabled:
        # Local sentence-transformers fallback would live here. For MVP we
        # return zeros; the dedupe stage tolerates this and falls back to
        # exact content_hash matching.
        return [0.0] * 16
    return await providers.call_embedding_provider(text)


def conservative_fallback(scope: str) -> LlmResponse:
    msg = (
        "Today's brief was generated in conservative mode — evidence sufficiency "
        "or validator stability fell below threshold. Manual review recommended."
    )
    return LlmResponse(
        text=msg,
        structured={"conservative": True, "scope": scope},
        provider="conservative",
        model="conservative",
        template_version="conservative@1",
        latency_ms=0,
        finish_reason="conservative",
    )


def _empty_dict():
    """Tiny shim to avoid Optional gymnastics where a dictionary is missing."""
    from briefalpha_api.anonymization.sensitive_entity_dictionary import (
        SensitiveEntityDictionary,
    )

    return SensitiveEntityDictionary()
