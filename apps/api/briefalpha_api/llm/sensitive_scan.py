"""Input/output sensitive scanners.

Input:
- alias_map real ticker literal MUST NOT appear (would mean we sent un-aliased data),
- `\d+%` numbers and a small keyword list trigger an audit warning,
- JSON body fields are validated against the response_schema's allowed keys.

Output:
- Reverse scan: any name in the sensitive_entity_dictionary or any real
  ticker found in the LLM response → wrapper retries once, then replaces
  with alias / placeholder.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from briefalpha_api.anonymization.alias import AliasContext
from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    SensitiveEntityDictionary,
)


class SensitiveInputViolation(RuntimeError):
    """Raised when sensitive content is found before wrapper sends to provider."""


@dataclass
class SensitiveScanReport:
    matched_terms: list[str]
    matched_pattern: list[str]


def scan_input_for_real_tickers(payload: dict, ctx: AliasContext) -> None:
    body = json.dumps(payload, ensure_ascii=False)
    for ticker in ctx.alias_to_ticker.values():
        if re.search(rf"\b{re.escape(ticker)}\b", body):
            raise SensitiveInputViolation(
                f"input contains real ticker '{ticker}'. anonymization layer is required."
            )


def scan_output_for_sensitive_terms(
    text: str,
    *,
    dictionary: SensitiveEntityDictionary,
) -> SensitiveScanReport:
    matched_terms: list[str] = []
    for name in dictionary.all_names():
        if name and name in text:
            matched_terms.append(name)
    pct = re.findall(r"\b\d+(\.\d+)?%", text)
    return SensitiveScanReport(matched_terms=matched_terms, matched_pattern=pct)


def scrub_output(
    text: str,
    *,
    dictionary: SensitiveEntityDictionary,
    ctx: AliasContext | None,
    placeholder: str = "[redacted]",
) -> str:
    """Replace every dictionary name in `text`. If alias_context is supplied,
    map dictionary name → ticker → alias; otherwise use placeholder."""
    out = text
    for name in sorted(dictionary.all_names(), key=len, reverse=True):
        if not name or name not in out:
            continue
        ticker = dictionary.lookup_name(name)
        repl = placeholder
        if ctx and ticker and ticker in ctx.ticker_to_alias:
            repl = ctx.ticker_to_alias[ticker]
        out = out.replace(name, repl)
    return out
