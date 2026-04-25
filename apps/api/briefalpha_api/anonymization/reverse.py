"""Safe reverse-alias.

Per design.md §5 / task 3.8:
- Only reverse aliases that appear within the supplied cited evidence's
  excerpt context — anchoring prevents LLM-fabricated aliases from being
  silently rendered as real tickers.
- Aliases NOT anchored in cited context are flagged `unsafe_generated_alias`
  and replaced with `[redacted]`.
- We do NOT do full-text string-replace; we only resolve aliases at known
  positions inside the LLM response that match cited-evidence anchors.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from briefalpha_api.anonymization.alias import AliasContext

_ALIAS_RE = re.compile(r"E_[0-9a-fA-F]{4}")


@dataclass
class ReverseAliasResult:
    text: str
    unsafe_generated_aliases: list[str]


def _anchored_aliases(
    ctx: AliasContext,
    *,
    cited_evidence_excerpts_aliased: list[str],
) -> set[str]:
    anchored: set[str] = set()
    for excerpt in cited_evidence_excerpts_aliased:
        for m in _ALIAS_RE.finditer(excerpt):
            if ctx.is_alias(m.group()):
                anchored.add(m.group())
    return anchored


def reverse_alias(
    text: str,
    ctx: AliasContext,
    *,
    cited_evidence_excerpts_aliased: list[str],
    redacted_token: str = "[redacted]",
) -> ReverseAliasResult:
    """Replace every anchored alias with its real ticker; redact every other
    alias-shaped token.
    """
    anchored = _anchored_aliases(ctx, cited_evidence_excerpts_aliased=cited_evidence_excerpts_aliased)
    unsafe: list[str] = []

    def repl(m: re.Match[str]) -> str:
        alias = m.group()
        if alias in anchored and ctx.is_alias(alias):
            return ctx.alias_to_ticker[alias]
        unsafe.append(alias)
        return redacted_token

    return ReverseAliasResult(text=_ALIAS_RE.sub(repl, text), unsafe_generated_aliases=unsafe)
