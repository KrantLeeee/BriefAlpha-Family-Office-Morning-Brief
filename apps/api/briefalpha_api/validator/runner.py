"""Validator runner — used by the LLM wrapper as the `accuracy_validate`
callback.

Chain order matters:
  citations → quote_span → numbers → polarity → time_window → sensitive

Time-window is checked after the cheap structural rules so we don't waste
trade-calendar lookups on responses that will fail upstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from briefalpha_api.anonymization.replace import Segment
from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    SensitiveEntityDictionary,
)
from briefalpha_api.llm.sensitive_scan import scan_output_for_sensitive_terms
from briefalpha_api.validator.citations import validate_citations
from briefalpha_api.validator.numbers import validate_numbers
from briefalpha_api.validator.polarity import validate_polarity
from briefalpha_api.validator.quote_span import validate_quote_span
from briefalpha_api.validator.time_window import (
    TimeWindowRule,
    validate_time_window,
)


@dataclass
class ValidationResult:
    ok: bool
    reason: str | None
    rules_passed: list[str] = field(default_factory=list)


@dataclass
class ValidationFailure(Exception):  # type: ignore[misc]
    reason: str


@dataclass(frozen=True)
class EvidencePoolEntry:
    """Just enough metadata for time-window evaluation."""
    source_tier: str
    asset_class: str | None
    published_at: datetime | None


# Source-tier → time-window rule. Asset-class can refine in the future
# (e.g. crypto would need a different rule); for the MVP universe the
# tier alone determines freshness expectations.
_TIER_TO_RULE = {
    "official": TimeWindowRule.OFFICIAL_RECENT,
    "news": TimeWindowRule.NEWS_RECENT,
    "market": TimeWindowRule.MARKET_OVERNIGHT,
    "research": TimeWindowRule.RESEARCH_PDF_30D,
}


def validate_response(
    *,
    structured: dict[str, Any],
    pool_ids: set[str],
    scope: str,
    quote_span_segments: list[Segment] | None,
    excerpt_text: str,
    answer_text: str,
    quote_span_aliased: tuple[int, int] | None,
    sensitive_dict: SensitiveEntityDictionary,
    pool_metadata: dict[str, EvidencePoolEntry] | None = None,
    brief_freeze_at_hkt: datetime | None = None,
) -> ValidationResult:
    rules_passed: list[str] = []

    ok, reason = validate_citations(structured=structured, pool_ids=pool_ids, scope=scope)
    if not ok:
        return ValidationResult(False, reason, rules_passed)
    rules_passed.append("citations")

    ok, reason = validate_quote_span(
        quote_span_aliased=quote_span_aliased,
        segments=quote_span_segments or [],
        excerpt_length_original=len(excerpt_text),
    )
    if not ok:
        return ValidationResult(False, reason, rules_passed)
    rules_passed.append("quote_span")

    ok, reason = validate_numbers(answer_text=answer_text, excerpt_text=excerpt_text)
    if not ok:
        return ValidationResult(False, reason, rules_passed)
    rules_passed.append("numbers")

    ok, reason = validate_polarity(answer_text=answer_text, excerpt_text=excerpt_text)
    if not ok:
        return ValidationResult(False, reason, rules_passed)
    rules_passed.append("polarity")

    if pool_metadata and brief_freeze_at_hkt is not None:
        cited_ids: list[str] = list(structured.get("cited_evidence_ids", []))
        if scope == "stage_b":
            for j in structured.get("judgements", []):
                cited_ids.extend(j.get("cited_evidence_ids", []))
        for eid in set(cited_ids):
            entry = pool_metadata.get(eid)
            if entry is None:
                continue
            rule = _TIER_TO_RULE.get(entry.source_tier)
            if rule is None:
                continue
            ok, reason = validate_time_window(
                rule=rule,
                evidence_published_at=entry.published_at,
                brief_freeze_at_hkt=brief_freeze_at_hkt,
            )
            if not ok:
                return ValidationResult(False, reason, rules_passed)
        rules_passed.append("time_window")

    report = scan_output_for_sensitive_terms(answer_text, dictionary=sensitive_dict)
    if report.matched_terms:
        return ValidationResult(False, f"sensitive_output:{report.matched_terms[:3]}", rules_passed)
    rules_passed.append("sensitive_output")

    return ValidationResult(True, None, rules_passed)
