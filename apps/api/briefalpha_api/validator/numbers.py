"""validator.numbers — numeric / unit consistency around quote_span ±120 chars.

Scope: we ONLY check numbers that carry a unit (`%`, `bps`, `x`, `亿`, `$`,
etc.). Unit-less integers / decimals are left alone — they're overwhelmingly
narrative ("过去 12 个月", "第 3 季度", a stripped price like `424.62` whose
matching `$` sits on the other side of the regex anchor) and produced
~100% false-positive rejections in production audit logs (see git history of
this file). The primary anti-hallucination guarantee is still that the LLM
only sees the cited excerpts — this validator's job is to catch the obvious
"5%/8.4bp/3x" fabrications that slip through.
"""
from __future__ import annotations

import re

# Number followed by a unit. Unit is REQUIRED — see module docstring.
# Currency markers can sit on either side of the number, so we additionally
# scan for `$123.45` style amounts via _CURRENCY_PREFIX_RE below.
_NUMBER_WITH_UNIT_RE = re.compile(
    r"(?P<num>-?\d+(?:\.\d+)?)\s*(?P<unit>%|bps?|bp|x|倍|亿|万|千|美元|港元|人民币|元|US\$|HK\$|\$)",
    re.IGNORECASE,
)
# Currency marker before the number (Western convention: `$424.62`, `HK$70.40`).
_CURRENCY_PREFIX_RE = re.compile(
    r"(?P<unit>US\$|HK\$|\$)\s*(?P<num>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_ANY_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

# Canonical unit normalization: same economic claim must compare equal whether
# the writer used the Western or Chinese form. We deliberately collapse `$`
# and `美元` into one bucket — without this, English excerpts and Chinese
# answers would never match.
_UNIT_CANON = {
    "$": "usd", "us$": "usd", "美元": "usd", "元": "usd",
    "hk$": "hkd", "港元": "hkd",
    "人民币": "cny",
    "bp": "bp", "bps": "bp",
    "x": "x", "倍": "x",
}


def _canon_unit(u: str) -> str:
    return _UNIT_CANON.get(u.lower(), u.lower())


def _terms(text: str) -> set[tuple[str, str]]:
    """Return `{(number, unit_canonical)}` for every unit-bearing numeric phrase."""
    out: set[tuple[str, str]] = set()
    for m in _NUMBER_WITH_UNIT_RE.finditer(text):
        out.add((m.group("num"), _canon_unit(m.group("unit"))))
    for m in _CURRENCY_PREFIX_RE.finditer(text):
        out.add((m.group("num"), _canon_unit(m.group("unit"))))
    return out


def _unitless_numbers(text: str) -> list[float]:
    spans_with_units: list[tuple[int, int]] = []
    for m in _NUMBER_WITH_UNIT_RE.finditer(text):
        spans_with_units.append(m.span())
    for m in _CURRENCY_PREFIX_RE.finditer(text):
        spans_with_units.append(m.span())

    nums: list[float] = []
    for m in _ANY_NUMBER_RE.finditer(text):
        if any(start <= m.start() and m.end() <= end for start, end in spans_with_units):
            continue
        try:
            nums.append(float(m.group(0)))
        except ValueError:
            continue
    return nums


def _numeric_match(left: str, right: str) -> bool:
    try:
        lval = float(left)
        rval = float(right)
    except ValueError:
        return False
    tolerance = max(0.01, abs(rval) * 0.0001)
    return abs(lval - rval) <= tolerance


def _term_supported_by_excerpt(
    term: tuple[str, str],
    excerpt_terms: set[tuple[str, str]],
    excerpt_unitless: list[float],
) -> bool:
    num, unit = term
    if term in excerpt_terms:
        return True
    if any(unit == ex_unit and _numeric_match(num, ex_num) for ex_num, ex_unit in excerpt_terms):
        return True
    if unit in {"usd", "hkd", "cny"}:
        try:
            val = float(num)
        except ValueError:
            return False
        return any(abs(val - ex_val) <= max(0.01, abs(ex_val) * 0.0001) for ex_val in excerpt_unitless)
    return False


def validate_numbers(
    *,
    answer_text: str,
    excerpt_text: str,
) -> tuple[bool, str | None]:
    """Every UNIT-BEARING numeric phrase in `answer_text` must also appear
    (with the same unit) in `excerpt_text`. Unit-less digits are ignored.

    Returns `(True, None)` on pass; on fail, the reason carries up to 3
    sample missing terms for the audit log.
    """
    excerpt_terms = _terms(excerpt_text)
    excerpt_unitless = _unitless_numbers(excerpt_text)
    missing = {
        term
        for term in _terms(answer_text)
        if not _term_supported_by_excerpt(term, excerpt_terms, excerpt_unitless)
    }
    if missing:
        return False, f"numbers:missing_in_excerpt:{sorted(missing)[:3]}"
    return True, None
