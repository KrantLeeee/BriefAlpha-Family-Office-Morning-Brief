"""ticker / company name replacement + AliasedEvidence model + segment list.

Per design.md §5 / task 3.6:

- For each replacement, emit a `Segment(field, orig_start, orig_end,
  alias_start, alias_end, original_text, alias)`.
- Multiple occurrences (or multi-variant aliases collapsed to the same
  alias) emit independent segments.
- `aliased_to_original(span, segments)` is the ONLY allowed mapping back to
  the original quote_span. Cumulative-offset shortcuts MUST be cross-checked
  against this segment-based algorithm in unit tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from briefalpha_api.anonymization.alias import AliasContext


@dataclass(frozen=True)
class Segment:
    field: str
    orig_start: int
    orig_end: int
    alias_start: int
    alias_end: int
    original_text: str
    alias: str


def _build_pattern(terms: list[str]) -> re.Pattern[str] | None:
    if not terms:
        return None
    # Sort longest-first so "腾讯控股" wins over "腾讯".
    sorted_terms = sorted(set(terms), key=len, reverse=True)
    escaped = [re.escape(t) for t in sorted_terms]
    return re.compile("|".join(escaped))


def _candidate_terms(ctx: AliasContext) -> list[str]:
    return list(ctx.ticker_to_alias.keys()) + list(ctx.name_to_alias.keys())


def replace_in_text(
    text: str,
    ctx: AliasContext,
    *,
    field: str,
) -> tuple[str, list[Segment]]:
    """Apply alias substitutions and return the new string + segment list."""
    pattern = _build_pattern(_candidate_terms(ctx))
    if pattern is None:
        return text, []

    out_parts: list[str] = []
    segments: list[Segment] = []
    cursor = 0
    alias_cursor = 0

    for match in pattern.finditer(text):
        start, end = match.span()
        out_parts.append(text[cursor:start])
        alias_cursor += start - cursor

        original = match.group()
        alias = ctx.ticker_to_alias.get(original) or ctx.name_to_alias.get(original)
        if alias is None:
            # Defensive: pattern matched but lookup failed → skip rewrite.
            out_parts.append(original)
            alias_cursor += len(original)
            cursor = end
            continue

        out_parts.append(alias)
        segments.append(
            Segment(
                field=field,
                orig_start=start,
                orig_end=end,
                alias_start=alias_cursor,
                alias_end=alias_cursor + len(alias),
                original_text=original,
                alias=alias,
            )
        )
        alias_cursor += len(alias)
        cursor = end

    out_parts.append(text[cursor:])
    return "".join(out_parts), segments


def aliased_to_original(
    span: tuple[int, int],
    segments: list[Segment],
) -> tuple[int, int] | None:
    """Map an alias-coordinate span back to original-coordinate span.

    Returns None if the span:
      - falls inside a single alias token (cannot be mapped to a sub-span),
      - crosses two distinct alias regions in a way we can't preserve,
      - or covers a region with no segment information at all when we
        cannot reconstruct the cumulative offset.

    The function is conservative: when in doubt, return None so the caller
    flags the LLM output for retry rather than silently shifting.
    """
    a_start, a_end = span
    if a_start > a_end:
        return None

    # Reject if either endpoint lands strictly INSIDE an alias span.
    for seg in segments:
        if seg.alias_start < a_start < seg.alias_end:
            return None
        if seg.alias_start < a_end < seg.alias_end:
            return None

    # Compute cumulative deltas applied by segments that ended at or before
    # each endpoint. delta = alias_len - orig_len for that segment.
    def offset_at(alias_pos: int) -> int | None:
        delta = 0
        for seg in segments:
            if seg.alias_end <= alias_pos:
                delta += (seg.alias_end - seg.alias_start) - (seg.orig_end - seg.orig_start)
            elif seg.alias_start <= alias_pos < seg.alias_end:
                # Endpoint inside alias — already rejected above, so this
                # branch shouldn't fire, but guard anyway.
                return None
        return alias_pos - delta

    o_start = offset_at(a_start)
    o_end = offset_at(a_end)
    if o_start is None or o_end is None:
        return None
    if o_start > o_end:
        return None
    return (o_start, o_end)


# ---------------------------------------------------------------------------
# AliasedEvidence pydantic model (whitelist)
# ---------------------------------------------------------------------------

ALLOWED_FIELDS = (
    "evidence_id",
    "title_aliased",
    "excerpt_aliased",
    "quote_span_aliased",
    "source_tier",
    "asset_class",
    "published_at",
)

SourceTier = Literal["market", "news", "official", "research"]


class AliasedEvidence(BaseModel):
    """The ONLY evidence shape allowed in LLM payloads."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    title_aliased: str
    excerpt_aliased: str
    quote_span_aliased: tuple[int, int] | None = None
    source_tier: SourceTier
    asset_class: str | None = None
    published_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _strip_unknown(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        return {k: v for k, v in data.items() if k in ALLOWED_FIELDS}


def build_aliased_evidence(
    *,
    evidence_id: str,
    title: str,
    excerpt: str,
    source_tier: SourceTier,
    asset_class: str | None,
    published_at: datetime | None,
    ctx: AliasContext,
    quote_span_original: tuple[int, int] | None = None,
) -> tuple[AliasedEvidence, list[Segment]]:
    """One-shot helper: alias title + excerpt, project quote_span_original
    forward into alias coordinates, return both the AliasedEvidence and
    accumulated segments needed for `aliased_to_original` later.
    """
    title_aliased, title_segs = replace_in_text(title, ctx, field="title")
    excerpt_aliased, excerpt_segs = replace_in_text(excerpt, ctx, field="excerpt")
    segs = [*title_segs, *excerpt_segs]

    quote_span_aliased: tuple[int, int] | None = None
    if quote_span_original is not None:
        # Project [o_start, o_end] forward through excerpt segments.
        o_start, o_end = quote_span_original
        delta = 0
        for s in excerpt_segs:
            if s.orig_end <= o_start:
                delta += (s.alias_end - s.alias_start) - (s.orig_end - s.orig_start)
        new_start = o_start + delta
        delta_end = 0
        for s in excerpt_segs:
            if s.orig_end <= o_end:
                delta_end += (s.alias_end - s.alias_start) - (s.orig_end - s.orig_start)
        new_end = o_end + delta_end
        quote_span_aliased = (new_start, new_end)

    aliased = AliasedEvidence(
        evidence_id=evidence_id,
        title_aliased=title_aliased,
        excerpt_aliased=excerpt_aliased,
        quote_span_aliased=quote_span_aliased,
        source_tier=source_tier,
        asset_class=asset_class,
        published_at=published_at,
    )
    return aliased, segs
