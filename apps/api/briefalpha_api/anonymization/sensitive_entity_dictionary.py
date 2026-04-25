"""Daily-refreshed sensitive entity dictionary.

Per design.md §4.2:
- Refreshed daily at 06:50 HKT before ingestion runs.
- Source: yfinance `symbol/longName/shortName/quoteType/exchange` for every
  ticker in the universe + `company_alias_zh.yml` (Chinese aliases).
- HK variants (`.HK`, leading-zero stripped/padded, HKEX prefix) included.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from briefalpha_api.settings import CONFIG_DIR


@dataclass
class SensitiveEntityDictionary:
    """For each ticker, the set of name variants that MUST be scrubbed."""

    by_ticker: dict[str, list[str]] = field(default_factory=dict)
    name_to_ticker: dict[str, str] = field(default_factory=dict)

    def names_for(self, ticker: str) -> list[str]:
        return self.by_ticker.get(ticker, [])

    def all_names(self) -> list[str]:
        return list(self.name_to_ticker.keys())

    def lookup_name(self, name: str) -> str | None:
        return self.name_to_ticker.get(name)


@lru_cache(maxsize=1)
def _load_zh_aliases() -> dict[str, list[str]]:
    path: Path = CONFIG_DIR / "company_alias_zh.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_sensitive_entity_dictionary(
    *,
    universe_tickers: list[str],
    yfinance_names: dict[str, dict[str, str]] | None = None,
) -> SensitiveEntityDictionary:
    """Build a sensitive dictionary for the given universe.

    `yfinance_names` should map ticker → { longName, shortName }; if absent
    we fall back to `company_alias_zh.yml` only (offline-safe).
    """
    zh = _load_zh_aliases()
    yfn = yfinance_names or {}

    by_ticker: dict[str, list[str]] = {}
    name_to_ticker: dict[str, str] = {}

    for ticker in universe_tickers:
        names: list[str] = []
        for nm in zh.get(ticker, []):
            names.append(nm)
        info = yfn.get(ticker, {})
        for key in ("longName", "shortName"):
            if info.get(key):
                names.append(info[key])
        # Also push the ticker itself (case-insensitive) so loose mentions
        # like "NVDA" still get scrubbed even with no alias bindings yet.
        names.append(ticker)

        # De-dupe while preserving order
        seen: set[str] = set()
        unique = []
        for nm in names:
            key = nm.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(nm)
        by_ticker[ticker] = unique
        for nm in unique:
            name_to_ticker.setdefault(nm, ticker)

    return SensitiveEntityDictionary(by_ticker=by_ticker, name_to_ticker=name_to_ticker)
