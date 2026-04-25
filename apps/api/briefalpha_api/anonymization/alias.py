"""Per-brief AliasContext."""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    SensitiveEntityDictionary,
)


@dataclass
class AliasContext:
    """Bidirectional alias mapping with brief-scoped lifetime.

    `ticker_to_alias` maps every ticker (and its variants) to a randomly
    generated `E_xxxx` token. `alias_to_ticker` is the inverse.
    `name_to_alias` maps each company-name variant (English / Chinese /
    short / exchange-prefixed) to the SAME alias as its ticker — that way
    "Tencent" / "腾讯" / "0700.HK" all collapse to one alias.
    `entity_dictionary` is bundled in for `replace_in_text` & sensitive
    scans.
    """

    brief_id: str
    ticker_to_alias: dict[str, str] = field(default_factory=dict)
    alias_to_ticker: dict[str, str] = field(default_factory=dict)
    name_to_alias: dict[str, str] = field(default_factory=dict)
    entity_dictionary: SensitiveEntityDictionary | None = None

    def alias_for(self, term: str) -> str | None:
        """Find an alias for either a ticker or a company-name variant."""
        if term in self.ticker_to_alias:
            return self.ticker_to_alias[term]
        return self.name_to_alias.get(term)

    def is_alias(self, token: str) -> bool:
        return token in self.alias_to_ticker

    def to_dict(self) -> dict:
        return {
            "brief_id": self.brief_id,
            "ticker_to_alias": self.ticker_to_alias,
            "alias_to_ticker": self.alias_to_ticker,
            "name_to_alias": self.name_to_alias,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AliasContext":
        return cls(
            brief_id=data["brief_id"],
            ticker_to_alias=data["ticker_to_alias"],
            alias_to_ticker=data["alias_to_ticker"],
            name_to_alias=data["name_to_alias"],
        )


def _hex_alias() -> str:
    return f"E_{secrets.token_hex(2)}"


def _hk_variants(ticker: str) -> list[str]:
    """Generate HK exchange variants for `0700.HK`:

    - `0700.HK`
    - `00700.HK` (with leading zeros padded to 5)
    - `HKEX:0700`
    - `HK:0700`
    - `700.HK` (stripped of leading zeros)
    """
    if not ticker.endswith(".HK"):
        return [ticker]
    code = ticker[:-3]
    stripped = code.lstrip("0") or "0"
    padded = code.zfill(5)
    return [
        ticker,
        f"{stripped}.HK",
        f"{padded}.HK",
        f"HKEX:{stripped}",
        f"HKEX:{padded}",
        f"HK:{stripped}",
        f"HK:{padded}",
    ]


def make_alias_context(
    *,
    brief_id: str,
    universe_tickers: list[str],
    external_tickers: list[str] | None = None,
    entity_dictionary: SensitiveEntityDictionary,
) -> AliasContext:
    """Generate fresh aliases. Both universe + external tickers (from
    research PDFs) get the same `E_xxxx` treatment so later scans can match
    either against the alias map.
    """
    ctx = AliasContext(brief_id=brief_id, entity_dictionary=entity_dictionary)
    used: set[str] = set()

    for ticker in (*universe_tickers, *(external_tickers or [])):
        if ticker in ctx.ticker_to_alias:
            continue
        while True:
            alias = _hex_alias()
            if alias not in used:
                used.add(alias)
                break

        # All HK variants of one ticker collapse to one alias.
        for variant in _hk_variants(ticker):
            ctx.ticker_to_alias[variant] = alias
        ctx.alias_to_ticker[alias] = ticker

        # Bind every known name variant to the same alias.
        for name in entity_dictionary.names_for(ticker):
            ctx.name_to_alias[name] = alias

    return ctx
