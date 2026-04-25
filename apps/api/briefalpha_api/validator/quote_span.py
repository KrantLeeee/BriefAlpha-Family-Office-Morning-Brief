"""validator.quote_span — calls anonymization's segment-based mapper.

Per design.md §5: validator MUST NOT implement its own offset math.
"""
from __future__ import annotations

from briefalpha_api.anonymization.replace import Segment, aliased_to_original


def validate_quote_span(
    *,
    quote_span_aliased: tuple[int, int] | None,
    segments: list[Segment],
    excerpt_length_original: int,
) -> tuple[bool, str | None]:
    if quote_span_aliased is None:
        return True, None
    mapped = aliased_to_original(quote_span_aliased, segments)
    if mapped is None:
        return False, "quote_span:not_locatable"
    if not (0 <= mapped[0] <= mapped[1] <= excerpt_length_original):
        return False, "quote_span:out_of_bounds"
    return True, None
