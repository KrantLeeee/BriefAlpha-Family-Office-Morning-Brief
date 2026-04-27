"""Market adapter: yfinance primary; stooq / Finnhub / Alpha Vantage backup."""
from __future__ import annotations

import csv
import io
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from briefalpha_api.ingestion.base import IngestionAdapter, RawItem, is_provider_enabled
from briefalpha_api.portfolio.models import PrivacySafeUniverse, UniverseTicker

log = logging.getLogger("briefalpha.ingestion")

_STOOQ_QUOTE_URL = "https://stooq.com/q/l/"


class MarketAdapter(IngestionAdapter):
    source_tier = "market"
    source_name = "yfinance"

    async def fetch(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        items: list[RawItem] = []
        now = datetime.now(UTC)
        for t in universe.tickers:
            item = await self._fetch_one(t, now)
            if item:
                items.append(item)
        return items

    async def _fetch_one(self, t: UniverseTicker, now: datetime) -> RawItem | None:
        if is_provider_enabled("yfinance"):
            item = self._fetch_yfinance(t, now)
            if item:
                return item
        if is_provider_enabled("stooq"):
            return await self._fetch_stooq(t, now)
        return None

    def _fetch_yfinance(self, t: UniverseTicker, now: datetime) -> RawItem | None:
        try:
            import yfinance  # type: ignore[import-untyped]
        except ImportError:
            return None
        logging.getLogger("yfinance").setLevel(logging.ERROR)

        try:
            tk = yfinance.Ticker(t.ticker)
            fast = tk.fast_info
            last_price_raw = _fast_info_get(fast, "last_price")
            previous_close_raw = _fast_info_get(fast, "previous_close")
            day_high_raw = _fast_info_get(fast, "day_high")
            day_low_raw = _fast_info_get(fast, "day_low")
            if not any(
                _is_number(v)
                for v in (last_price_raw, previous_close_raw, day_high_raw, day_low_raw)
            ):
                log.debug("yfinance returned no quote fields for %s", t.ticker)
                return None

            last_price = _fmt_price(last_price_raw)
            previous_close = _fmt_price(previous_close_raw)
            day_high = _fmt_price(day_high_raw)
            day_low = _fmt_price(day_low_raw)
            last_volume = _fast_info_get(fast, "last_volume")
            excerpt = (
                f"{t.ticker} 上次收盘 {previous_close}; "
                f"日内 {day_high} / {day_low}; "
                f"成交量 {last_volume or 'n/a'}."
            )
            return RawItem(
                source_name="yfinance",
                source_tier="market",
                source_url=f"yfinance://{t.ticker}",
                title=f"{t.ticker} 隔夜估算 {last_price}",
                excerpt=excerpt,
                detected_tickers=[t.ticker],
                asset_class=t.asset_class,
                published_at=now,
                fetched_at=now,
            )
        except Exception as exc:  # noqa: BLE001
            # Per task 4.5 single-ticker failure must not poison the batch.
            log.debug("yfinance fetch skipped for %s: %r", t.ticker, exc)
            return None

    async def _fetch_stooq(self, t: UniverseTicker, now: datetime) -> RawItem | None:
        symbol = _stooq_symbol(t)
        if not symbol:
            return None
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    _STOOQ_QUOTE_URL,
                    params={"s": symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"},
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.debug("stooq fetch skipped for %s: %r", t.ticker, exc)
            return None

        row = _parse_stooq_csv(resp.text)
        if not row:
            log.debug("stooq returned no quote fields for %s", t.ticker)
            return None

        close = _fmt_price(row.get("Close"))
        high = _fmt_price(row.get("High"))
        low = _fmt_price(row.get("Low"))
        open_ = _fmt_price(row.get("Open"))
        volume = row.get("Volume") or "n/a"
        excerpt = (
            f"{t.ticker} Stooq 收盘 {close}; "
            f"日内 {high} / {low}; 开盘 {open_}; 成交量 {volume}."
        )
        return RawItem(
            source_name="stooq",
            source_tier="market",
            source_url=f"https://stooq.com/q/?s={symbol}",
            title=f"{t.ticker} 备用行情 {close}",
            excerpt=excerpt,
            detected_tickers=[t.ticker],
            asset_class=t.asset_class,
            published_at=now,
            fetched_at=now,
        )


def _fmt_price(value) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _fast_info_get(fast: Any, key: str) -> Any:
    if isinstance(fast, dict):
        return fast.get(key)
    try:
        return getattr(fast, key)
    except Exception:  # noqa: BLE001
        return None


def _stooq_symbol(t: UniverseTicker) -> str | None:
    ticker = t.ticker.strip().lower()
    if t.asset_class not in {"us_equity", "us_equity_etf"}:
        return None
    if "." in ticker:
        return ticker
    return f"{ticker}.us"


def _parse_stooq_csv(raw: str) -> dict[str, str] | None:
    reader = csv.DictReader(io.StringIO(raw))
    row = next(reader, None)
    if not row or row.get("Close") in {None, "", "N/D"}:
        return None
    return row
