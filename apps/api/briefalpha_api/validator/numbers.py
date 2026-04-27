"""validator.numbers — numeric / unit consistency around quote_span ±120 chars.

Scope: we ONLY check numbers that carry a unit (`%`, `bps`, `x`, `亿`, `$`,
etc.). Unit-less integers / decimals are left alone — they're overwhelmingly
narrative ("过去 12 个月", "第 3 季度", a stripped price like `424.62` whose
matching `$` sits on the other side of the regex anchor) and produced
~100% false-positive rejections in production audit logs (see git history of
this file). The primary anti-hallucination guarantee is still that the LLM
only sees the cited excerpts — this validator's job is to catch the obvious
"5%/8.4bp/3x" fabrications that slip through.

Magnitude normalization: an answer phrased as `57.06 亿` and an excerpt
phrased as `$5,706 million` describe the same quantity, so the validator
canonicalizes both to a scaled `(value, currency)` tuple before comparing.
Without this, every legitimate billion ↔ 亿 unit conversion the LLM
performed in Stage B was rejected (see audit log 2026-04-27).
"""
from __future__ import annotations

import re

# Number with optional thousand separators ("5,706" or "5，706") and decimals.
_NUM_PATTERN = r"-?\d+(?:[,，]\d{3})*(?:\.\d+)?"

# Magnitude word → multiplier. Keys are matched case-insensitively and
# longest-first so "万亿" beats "万", "百万" beats "百", etc.
_MAGNITUDE: dict[str, float] = {
    "千": 1e3,
    "万": 1e4,
    "百万": 1e6,
    "million": 1e6,
    "mn": 1e6,
    "亿": 1e8,
    "十亿": 1e9,
    "billion": 1e9,
    "bn": 1e9,
    "万亿": 1e12,
    "trillion": 1e12,
}

# Currency token → canonical code. Same comparison treatment as magnitude.
_CURRENCY: dict[str, str] = {
    "$": "usd",
    "us$": "usd",
    "美元": "usd",
    "元": "usd",
    "hk$": "hkd",
    "港元": "hkd",
    "人民币": "cny",
    "rmb": "cny",
}

_MAG_PATTERN = "|".join(re.escape(k) for k in sorted(_MAGNITUDE, key=len, reverse=True))
_CURR_PATTERN = "|".join(re.escape(k) for k in sorted(_CURRENCY, key=len, reverse=True))

# Unit-less recurring categories — kept as separate compiled regexes so the
# fast path stays O(matches) and we don't have to disambiguate inside one
# giant alternation.
_PERCENT_RE = re.compile(rf"(?P<num>{_NUM_PATTERN})\s*(?:%|百分点)")
_BPS_RE = re.compile(rf"(?P<num>{_NUM_PATTERN})\s*(?:bps?|bp)", re.IGNORECASE)
_TIMES_RE = re.compile(rf"(?P<num>{_NUM_PATTERN})\s*(?:x|倍)", re.IGNORECASE)

# Currency / magnitude amount: optional currency prefix, number, optional
# magnitude word, optional currency suffix. We require AT LEAST one of
# {prefix, magnitude, suffix} to be present (checked in code) so unit-less
# integers don't get swept up.
_AMOUNT_RE = re.compile(
    rf"(?P<curr_pre>{_CURR_PATTERN})?\s*"
    rf"(?P<num>{_NUM_PATTERN})\s*"
    rf"(?P<mag>{_MAG_PATTERN})?\s*"
    rf"(?P<curr_post>{_CURR_PATTERN})?",
    re.IGNORECASE,
)

_BARE_NUM_RE = re.compile(_NUM_PATTERN)


def _to_float(s: str) -> float | None:
    s = s.replace(",", "").replace("，", "")
    try:
        return float(s)
    except ValueError:
        return None


def _spans_with_units(text: str) -> list[tuple[int, int]]:
    """All character spans that participate in a unit-bearing match.

    Used by `_unitless_numbers` to skip digits we already accounted for as
    part of a percent / bps / x / amount term.
    """
    spans: list[tuple[int, int]] = []
    for pat in (_PERCENT_RE, _BPS_RE, _TIMES_RE):
        for m in pat.finditer(text):
            spans.append(m.span())
    for m in _AMOUNT_RE.finditer(text):
        if m.group("curr_pre") or m.group("mag") or m.group("curr_post"):
            spans.append(m.span())
    return spans


def _terms(text: str) -> set[tuple[float, str]]:
    """Return `{(canonical_value, canonical_unit)}` for every numeric phrase.

    `canonical_value` is `raw_number * magnitude` so cross-form claims compare
    equal: `57.06 亿`, `$5.706 billion`, and `5,706 million 美元` all reduce
    to `(5.706e9, "usd")` (the second example) or `(5.706e9, "count")`
    (the first, which has no currency token).

    `canonical_unit` is one of: `%`, `bp`, `x`, `usd`, `hkd`, `cny`, or
    `count` (no currency given). The match step (`_term_supported_by_excerpt`)
    decides how strictly units must agree.
    """
    out: set[tuple[float, str]] = set()

    for m in _PERCENT_RE.finditer(text):
        v = _to_float(m.group("num"))
        if v is not None:
            out.add((v, "%"))
    for m in _BPS_RE.finditer(text):
        v = _to_float(m.group("num"))
        if v is not None:
            out.add((v, "bp"))
    for m in _TIMES_RE.finditer(text):
        v = _to_float(m.group("num"))
        if v is not None:
            out.add((v, "x"))

    # Don't emit an amount term if the same characters were already claimed
    # by a percent / bps / x match (e.g., "8 %" → keep (8, %), not also
    # something like (8, count)).
    consumed: list[tuple[int, int]] = []
    for pat in (_PERCENT_RE, _BPS_RE, _TIMES_RE):
        for m in pat.finditer(text):
            consumed.append(m.span())

    for m in _AMOUNT_RE.finditer(text):
        if not (m.group("curr_pre") or m.group("mag") or m.group("curr_post")):
            continue
        ms, me = m.span()
        if any(s <= ms and me <= e for s, e in consumed):
            continue
        raw = _to_float(m.group("num"))
        if raw is None:
            continue
        mag_token = m.group("mag")
        scale = _MAGNITUDE[mag_token.lower()] if mag_token else 1.0
        curr_token = (m.group("curr_pre") or m.group("curr_post") or "").lower()
        currency = _CURRENCY.get(curr_token, "count")
        out.add((raw * scale, currency))

    return out


def _unitless_numbers(text: str) -> list[float]:
    """Bare numbers in `text` that did NOT participate in a unit match.

    Kept as a fallback excerpt source for currency claims so yfinance-style
    excerpts (`AAPL 上次收盘 272.7`) can ground a Chinese answer like
    `272.7 美元` even though the excerpt has no `$` sign.
    """
    used = _spans_with_units(text)
    out: list[float] = []
    for m in _BARE_NUM_RE.finditer(text):
        ms, me = m.span()
        if any(s <= ms and me <= e for s, e in used):
            continue
        v = _to_float(m.group(0))
        if v is not None:
            out.append(v)
    return out


def _values_close(left: float, right: float, *, ratio: float = 0.005) -> bool:
    """Tolerant equality. 0.5% covers honest LLM rounding (`273.05999…`
    excerpt vs `273.06` answer) without letting `5%` slip past `8%`."""
    tolerance = max(0.01, abs(right) * ratio)
    return abs(left - right) <= tolerance


def _term_supported_by_excerpt(
    term: tuple[float, str],
    excerpt_terms: set[tuple[float, str]],
    excerpt_unitless: list[float],
) -> bool:
    val, unit = term

    # Strict-unit categories: never allow cross-unit borrowing.
    if unit in {"%", "bp", "x"}:
        return any(unit == eu and _values_close(val, ev) for ev, eu in excerpt_terms)

    # Currency / count: same-canonical-unit OR one side is the loose "count"
    # (no currency token written). This is what allows `57.06 亿` to ground
    # against an excerpt that writes `$5,706 million`.
    for ev, eu in excerpt_terms:
        if eu in {"%", "bp", "x"}:
            continue
        if unit != eu and unit != "count" and eu != "count":
            continue
        if _values_close(val, ev):
            return True

    # yfinance-style excerpt fallback: a currency answer can match a
    # unit-less excerpt number (legacy market-price behavior).
    if unit in {"usd", "hkd", "cny", "count"}:
        if any(_values_close(val, ev) for ev in excerpt_unitless):
            return True
    return False


def validate_numbers(
    *,
    answer_text: str,
    excerpt_text: str,
) -> tuple[bool, str | None]:
    """Every UNIT-BEARING numeric phrase in `answer_text` must also appear
    (with a comparable unit) in `excerpt_text`. Unit-less digits are ignored.

    Returns `(True, None)` on pass; on fail, the reason carries up to 3
    sample missing terms for the audit log.
    """
    excerpt_terms = _terms(excerpt_text)
    excerpt_unitless = _unitless_numbers(excerpt_text)
    missing = [
        term
        for term in _terms(answer_text)
        if not _term_supported_by_excerpt(term, excerpt_terms, excerpt_unitless)
    ]
    if missing:
        sample = sorted(missing, key=lambda t: -abs(t[0]))[:3]
        return False, f"numbers:missing_in_excerpt:{sample}"
    return True, None
