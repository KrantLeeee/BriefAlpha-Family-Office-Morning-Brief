"""Market adapter: yfinance primary; stooq / Finnhub / Alpha Vantage backup."""
from __future__ import annotations

from datetime import datetime, timezone

from briefalpha_api.ingestion.base import IngestionAdapter, RawItem, is_provider_enabled
from briefalpha_api.portfolio.models import PrivacySafeUniverse


class MarketAdapter(IngestionAdapter):
    source_tier = "market"
    source_name = "yfinance"

    async def fetch(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        if not is_provider_enabled("yfinance"):
            return []
        try:
            import yfinance  # type: ignore[import-untyped]
        except ImportError:
            return []

        items: list[RawItem] = []
        now = datetime.now(timezone.utc)
        for t in universe.tickers:
            try:
                tk = yfinance.Ticker(t.ticker)
                fast = tk.fast_info
                last_price = _fmt_price(fast.last_price)
                previous_close = _fmt_price(fast.previous_close)
                day_high = _fmt_price(fast.day_high)
                day_low = _fmt_price(fast.day_low)
                excerpt = (
                    f"{t.ticker} 上次收盘 {previous_close}; "
                    f"日内 {day_high} / {day_low}; "
                    f"成交量 {fast.last_volume}."
                )
                items.append(
                    RawItem(
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
                )
            except Exception:  # noqa: BLE001
                # Per task 4.5 single-ticker failure must not poison the batch.
                continue
        return items


def _fmt_price(value) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "n/a"
