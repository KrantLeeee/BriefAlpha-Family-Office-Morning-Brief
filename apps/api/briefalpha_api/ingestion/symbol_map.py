"""Ticker → external-identifier lookups (SEC CIK, HKEX stock code).

Canonical sources (refresh periodically):
- SEC: https://www.sec.gov/files/company_tickers.json
- HKEX: https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities

The mappings live in `data/symbol_maps/*.json` so they can be regenerated
without a code release. Lookups are intentionally lenient (case-insensitive
for US tickers) to absorb the various spellings that flow in from upstream
adapters.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache

from briefalpha_api.settings import SYMBOL_MAPS_DIR

log = logging.getLogger("briefalpha.ingestion")

_SEC_FILE = SYMBOL_MAPS_DIR / "sec_company_tickers.json"
_HKEX_FILE = SYMBOL_MAPS_DIR / "hkex_stock_codes.json"


def _load_json(path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("symbol_map: failed to load %s: %s", path, exc)
        return {"mappings": {}}


@lru_cache(maxsize=1)
def _sec_mappings() -> dict[str, str]:
    payload = _load_json(_SEC_FILE)
    raw = payload.get("mappings") if isinstance(payload, dict) else None
    # Backwards-compat: if the on-disk file is the raw SEC company_tickers.json
    # shape (numeric-string keys → {"cik_str", "ticker", ...}), transform inline
    # so existing broken downloads don't silently produce an empty map.
    if not raw and isinstance(payload, dict) and any(
        isinstance(v, dict) and "cik_str" in v and "ticker" in v
        for v in payload.values()
    ):
        log.warning(
            "symbol_map: %s is raw SEC JSON (no 'mappings' key); transforming inline",
            _SEC_FILE,
        )
        raw = {}
        for entry in payload.values():
            if (
                isinstance(entry, dict)
                and entry.get("ticker")
                and entry.get("cik_str") is not None
            ):
                raw[str(entry["ticker"]).upper()] = str(entry["cik_str"]).zfill(10)
    raw = raw or {}
    # Normalize to upper-case keys for case-insensitive lookup.
    return {str(k).upper(): str(v) for k, v in raw.items()}


@lru_cache(maxsize=1)
def _hkex_mappings() -> dict[str, str]:
    payload = _load_json(_HKEX_FILE)
    raw = payload.get("mappings", {}) if isinstance(payload, dict) else {}
    raw = raw or {}
    if not raw and _HKEX_FILE.exists():
        # Most common cause: the file on disk is the raw .xlsx download
        # (binary), so _load_json returned the empty default. Surface a
        # clear hint instead of failing silently.
        log.warning(
            "symbol_map: %s exists but has no 'mappings' key — likely a raw "
            ".xlsx download; run scheduler symbol-map refresh to transform.",
            _HKEX_FILE,
        )
    # HK tickers are the canonical "NNNN.HK" form; preserve case.
    return {str(k): str(v) for k, v in raw.items()}


def cik_for(ticker: str) -> str | None:
    """Return the 10-char zero-padded SEC CIK for a US ticker, or None."""
    if not ticker:
        return None
    return _sec_mappings().get(ticker.upper())


def hkex_code_for(ticker: str) -> str | None:
    """Return the 5-digit HKEX stock code for an .HK ticker, or None."""
    if not ticker:
        return None
    return _hkex_mappings().get(ticker)
