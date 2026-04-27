from __future__ import annotations

from datetime import UTC, datetime

import pytest

from briefalpha_api.ingestion import news
from briefalpha_api.ingestion.base import RawItem
from briefalpha_api.ingestion.news import NewsAdapter
from briefalpha_api.portfolio.models import PrivacySafeUniverse, UniverseTicker


@pytest.mark.asyncio
async def test_news_adapter_uses_keyed_fallback_before_google(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        news,
        "is_provider_enabled",
        lambda name: name in {"gdelt", "finnhub", "google_news_rss"},
    )

    adapter = NewsAdapter()
    universe = PrivacySafeUniverse(
        brief_id="2026-04-27",
        tickers=[UniverseTicker(ticker="NVDA", asset_class="us_equity")],
    )

    async def no_gdelt(_universe):
        return []

    async def finnhub_items(_universe):
        return [
            RawItem(
                source_name="finnhub",
                source_tier="news",
                source_url="https://example.com/nvda",
                title="NVDA news",
                excerpt="NVDA news",
                detected_tickers=["NVDA"],
                published_at=datetime.now(UTC),
                fetched_at=datetime.now(UTC),
            )
        ]

    async def google_should_not_run(_universe):
        raise AssertionError("google fallback should not run when Finnhub returns items")

    monkeypatch.setattr(adapter, "_fetch_gdelt", no_gdelt)
    monkeypatch.setattr(adapter, "_fetch_finnhub", finnhub_items)
    monkeypatch.setattr(adapter, "_fetch_google_rss", google_should_not_run)

    items = await adapter.fetch(universe)

    assert [item.source_name for item in items] == ["finnhub"]
