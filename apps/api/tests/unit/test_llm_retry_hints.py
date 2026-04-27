"""Wrapper retry feedback: when accuracy_validate rejects an attempt, the
next retry must see what was wrong via `prior_failure_hints` in the
user_payload. Without this, the wrapper retried with an identical prompt
and a deterministic validator failure (e.g., the model habitually rendered
`5,706 million` as `57.06 亿`) drove every Stage B call to conservative
fallback (see audit log 2026-04-27)."""
from __future__ import annotations

import json

import pytest

from briefalpha_api.llm import wrapper as wrapper_mod
from briefalpha_api.llm import providers as providers_mod
from briefalpha_api.llm.schema import LlmRequest, LlmResponse


def _make_request() -> LlmRequest:
    return LlmRequest(
        call_type="text",
        scope="stage_b",
        template_version="stage_b@test",
        system="test system",
        user_payload={"task": "test"},
        aliased_evidence=[],
        max_tokens=200,
        temperature=0.0,
    )


@pytest.mark.asyncio
async def test_failed_validation_records_hint_for_next_retry(monkeypatch) -> None:
    """The provider sees a fresh `prior_failure_hints` entry on attempt 2
    and 3 after the first response is rejected by `accuracy_validate`."""
    seen_hints_per_attempt: list[list[str]] = []

    async def echo_provider(req: LlmRequest, *, provider: str = "anthropic") -> LlmResponse:
        # Snapshot what the model would observe on this attempt.
        seen_hints_per_attempt.append(list(req.user_payload.get("prior_failure_hints", [])))
        stub = {"judgements": []}
        return LlmResponse(
            text=json.dumps(stub),
            structured=stub,
            cited_evidence_ids=[],
            provider="echo",
            model="echo",
            template_version=req.template_version,
            latency_ms=0,
            finish_reason="stub",
        )

    monkeypatch.setattr(providers_mod, "call_text_provider", echo_provider)

    async def always_reject(_resp: LlmResponse) -> tuple[bool, str]:
        return False, "numbers:missing_in_excerpt:[(570.06, '亿')]"

    req = _make_request()
    await wrapper_mod.call_text_llm(
        req,
        audit_ctx={"brief_id": "test", "audit_mode": "demo"},
        accuracy_validate=always_reject,
    )

    # MAX_RETRY_TEXT=3 → 3 attempts; first sees no hint, second/third see one.
    assert len(seen_hints_per_attempt) == wrapper_mod.MAX_RETRY_TEXT
    assert seen_hints_per_attempt[0] == []
    assert any("570.06" in h for h in seen_hints_per_attempt[1])
    assert any("不要把" in h or "禁止" in h for h in seen_hints_per_attempt[1])


@pytest.mark.asyncio
async def test_provider_error_does_not_pollute_retry_hints(monkeypatch) -> None:
    """Transient provider errors say nothing actionable about the answer's
    content, so they must NOT show up as a `prior_failure_hints` entry."""
    seen_hints_per_attempt: list[list[str]] = []
    call_count = {"n": 0}

    async def flaky_provider(req: LlmRequest, *, provider: str = "anthropic") -> LlmResponse:
        seen_hints_per_attempt.append(list(req.user_payload.get("prior_failure_hints", [])))
        call_count["n"] += 1
        if call_count["n"] == 1:
            from briefalpha_api.llm.schema import ProviderError
            raise ProviderError("transient")
        stub = {"judgements": [{"rank": 1, "level": "watch", "title": "ok", "reasoning_chain": {}, "cited_evidence_ids": ["a", "b"]}]}
        return LlmResponse(
            text=json.dumps(stub),
            structured=stub,
            cited_evidence_ids=[],
            provider="ok",
            model="ok",
            template_version=req.template_version,
            latency_ms=0,
            finish_reason="stop",
        )

    monkeypatch.setattr(providers_mod, "call_text_provider", flaky_provider)

    req = _make_request()
    await wrapper_mod.call_text_llm(
        req,
        audit_ctx={"brief_id": "test", "audit_mode": "demo"},
        accuracy_validate=None,
    )

    # Both attempts should observe an empty hints list — the provider error
    # is not a content failure the model can act on.
    assert seen_hints_per_attempt[0] == []
    assert seen_hints_per_attempt[1] == []


def test_failure_hint_translation_covers_known_validator_codes() -> None:
    """Spot-check the failure-code → instruction map. Unknown codes must
    return None so we don't bloat the prompt with noise."""
    assert wrapper_mod._failure_hint("accuracy:numbers:missing_in_excerpt:[…]")
    assert wrapper_mod._failure_hint("accuracy:citations:fewer_than_2_citations")
    assert wrapper_mod._failure_hint("accuracy:polarity:beat_vs_miss")
    assert wrapper_mod._failure_hint("accuracy:time_window:stale_news")
    assert wrapper_mod._failure_hint("sensitive_output:['MSFT']")
    assert wrapper_mod._failure_hint("provider_error:timeout") is None
