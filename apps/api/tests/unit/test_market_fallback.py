from __future__ import annotations

from datetime import UTC, datetime

import pytest

from briefalpha_api.ingestion import market
from briefalpha_api.ingestion.market import MarketAdapter
from briefalpha_api.portfolio.models import UniverseTicker


def test_stooq_symbol_maps_us_ticker_only() -> None:
    assert (
        market._stooq_symbol(
            UniverseTicker(ticker="NVDA", asset_class="us_equity")
        )
        == "nvda.us"
    )
    assert (
        market._stooq_symbol(
            UniverseTicker(ticker="0700.HK", asset_class="hk_equity")
        )
        is None
    )


def test_parse_stooq_csv_rejects_nd_rows() -> None:
    assert (
        market._parse_stooq_csv(
            "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
            "0700.HK,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n"
        )
        is None
    )


@pytest.mark.asyncio
async def test_market_adapter_uses_stooq_when_yfinance_has_no_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        market,
        "is_provider_enabled",
        lambda name: name in {"yfinance", "stooq"},
    )

    adapter = MarketAdapter()
    ticker = UniverseTicker(ticker="NVDA", asset_class="us_equity")

    monkeypatch.setattr(adapter, "_fetch_yfinance", lambda *_args: None)

    async def fake_stooq(
        t: UniverseTicker, now: datetime
    ) -> market.RawItem | None:
        return market.RawItem(
            source_name="stooq",
            source_tier="market",
            source_url="https://stooq.com/q/?s=nvda.us",
            title="NVDA 备用行情 208.27",
            excerpt="NVDA Stooq 收盘 208.27",
            detected_tickers=[t.ticker],
            asset_class=t.asset_class,
            published_at=now,
            fetched_at=now,
        )

    monkeypatch.setattr(adapter, "_fetch_stooq", fake_stooq)

    item = await adapter._fetch_one(ticker, datetime.now(UTC))

    assert item is not None
    assert item.source_name == "stooq"
