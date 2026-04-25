"""Validator runner — used by the LLM wrapper as the `accuracy_validate`
callback."""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class ValidationResult:
    ok: bool
    reason: str | None


@dataclass
class ValidationFailure(Exception):  # type: ignore[misc]
    reason: str


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
) -> ValidationResult:
    ok, reason = validate_citations(structured=structured, pool_ids=pool_ids, scope=scope)
    if not ok:
        return ValidationResult(False, reason)

    ok, reason = validate_quote_span(
        quote_span_aliased=quote_span_aliased,
        segments=quote_span_segments or [],
        excerpt_length_original=len(excerpt_text),
    )
    if not ok:
        return ValidationResult(False, reason)

    ok, reason = validate_numbers(answer_text=answer_text, excerpt_text=excerpt_text)
    if not ok:
        return ValidationResult(False, reason)

    ok, reason = validate_polarity(answer_text=answer_text, excerpt_text=excerpt_text)
    if not ok:
        return ValidationResult(False, reason)

    report = scan_output_for_sensitive_terms(answer_text, dictionary=sensitive_dict)
    if report.matched_terms:
        return ValidationResult(False, f"sensitive_output:{report.matched_terms[:3]}")

    return ValidationResult(True, None)
