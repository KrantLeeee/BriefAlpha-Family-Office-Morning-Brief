"""validator.numbers — numeric / unit consistency around quote_span ±120 chars."""
from __future__ import annotations

import re

# Match: integer, decimal, percent, basis-points, multipliers, currency
# amounts. We MUST require a unit on both sides for a successful match.
_NUMBER_RE = re.compile(
    r"(?P<num>-?\d+(?:\.\d+)?)\s*(?P<unit>%|bps?|bp|x|倍|亿|万|千|US\$|HK\$|\$)?",
    re.IGNORECASE,
)


def validate_numbers(
    *,
    answer_text: str,
    excerpt_text: str,
) -> tuple[bool, str | None]:
    """Every numeric+unit pair in `answer_text` must appear (with the same
    unit) somewhere in `excerpt_text`. We don't catch every edge case — the
    primary safety net is the LLM having seen only the excerpt — but this
    catches obvious "hallucinated 18% / 8.4bp / 5x" cases.
    """
    answer_terms = {(m.group("num"), (m.group("unit") or "").lower()) for m in _NUMBER_RE.finditer(answer_text)}
    excerpt_terms = {(m.group("num"), (m.group("unit") or "").lower()) for m in _NUMBER_RE.finditer(excerpt_text)}

    missing = answer_terms - excerpt_terms
    if missing:
        return False, f"numbers:missing_in_excerpt:{sorted(missing)[:3]}"
    return True, None
