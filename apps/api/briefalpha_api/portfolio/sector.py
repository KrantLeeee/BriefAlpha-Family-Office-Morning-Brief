"""Sector / industry / asset_class resolver."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from briefalpha_api.settings import CONFIG_DIR


@lru_cache(maxsize=1)
def _load_overrides() -> dict[str, dict[str, str]]:
    path: Path = CONFIG_DIR / "ticker_sector_overrides.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_sector(ticker: str, *, yfinance_sector: str | None = None) -> str:
    """Manual override beats yfinance; fall back to 'Unclassified'."""
    overrides = _load_overrides()
    entry = overrides.get(ticker)
    if entry and entry.get("sector"):
        return entry["sector"]
    if yfinance_sector:
        return yfinance_sector
    return "Unclassified"


def resolve_asset_class(ticker: str) -> str:
    overrides = _load_overrides()
    entry = overrides.get(ticker)
    if entry and entry.get("asset_class"):
        return entry["asset_class"]
    if ticker.endswith(".HK"):
        return "hk_equity"
    if ticker == "CASH":
        return "cash"
    return "us_equity"
