"""Standard fix for the source-name discrepancy: each news adapter must
populate `RawItem.source_name` with the *publisher* (Yahoo, Reuters,
nvidia.com, etc.) and stash the aggregator (finnhub / newsapi / gdelt /
google_news_rss) into `RawItem.fetched_via`.

Before this, every finnhub-fetched article carried `source_name="finnhub"`,
which made the evidence card label "finnhub" while the click-through took
the user to a Yahoo Finance article via finnhub's 302 redirector.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from briefalpha_api.ingestion import news
from briefalpha_api.ingestion.base import RawItem
from briefalpha_api.ingestion.news import (
    NewsAdapter,
    _google_rss_publisher,
    _publisher_from_url,
)
from briefalpha_api.ingestion.runner import _health_source_name
from briefalpha_api.portfolio.models import PrivacySafeUniverse, UniverseTicker


# ---------------------------------------------------------------------------
# _publisher_from_url
# ---------------------------------------------------------------------------


def test_publisher_from_url_strips_www_prefix() -> None:
    assert _publisher_from_url("https://www.reuters.com/article/foo") == "reuters.com"


def test_publisher_from_url_keeps_subdomain() -> None:
    """`finance.yahoo.com` is more useful than just `yahoo.com` — different
    sub-properties (sports, mail, etc.) live on the same root and the
    finance vertical is the relevant signal for an investment evidence."""
    assert _publisher_from_url("https://finance.yahoo.com/news/x") == "finance.yahoo.com"


def test_publisher_from_url_rejects_aggregator_hosts() -> None:
    """finnhub.io / news.google.com tell the user nothing about the real
    article — falling back to them defeats the whole point of this fix."""
    assert _publisher_from_url("https://finnhub.io/api/news?id=abc") is None
    assert _publisher_from_url("https://news.google.com/rss/articles/CBM") is None


def test_publisher_from_url_handles_empty_and_invalid() -> None:
    assert _publisher_from_url(None) is None
    assert _publisher_from_url("") is None
    assert _publisher_from_url("not a url") is None


# ---------------------------------------------------------------------------
# _google_rss_publisher
# ---------------------------------------------------------------------------


def test_google_rss_publisher_dict_shape() -> None:
    entry = {"source": {"title": "Reuters", "href": "https://www.reuters.com"}}
    assert _google_rss_publisher(entry) == "Reuters"


def test_google_rss_publisher_string_shape() -> None:
    entry = {"source": "Bloomberg"}
    assert _google_rss_publisher(entry) == "Bloomberg"


def test_google_rss_publisher_attribute_shape() -> None:
    entry = SimpleNamespace(source=SimpleNamespace(title="The Verge"))
    assert _google_rss_publisher(entry) == "The Verge"


def test_google_rss_publisher_missing_returns_none() -> None:
    assert _google_rss_publisher({}) is None
    assert _google_rss_publisher({"source": None}) is None


# ---------------------------------------------------------------------------
# Adapter integration with mocked httpx — finnhub's `source` field wins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finnhub_adapter_uses_source_field_as_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finnhub returns each article with its own `source` (publisher) field.
    The adapter must surface that in `source_name` and tag the aggregator
    in `fetched_via`."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test-token")

    # Mock httpx so we don't hit the network. Returns one article with
    # source="Yahoo" and a finnhub redirector URL.
    captured_response = [
        {
            "headline": "NVDA hits new high",
            "summary": "NVDA price action",
            "source": "Yahoo",
            "url": "https://finnhub.io/api/news?id=abc",
            "datetime": int(datetime.now(UTC).timestamp()),
        }
    ]

    class _FakeResponse:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, _url, params=None):
            return _FakeResponse(captured_response)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    adapter = NewsAdapter()
    universe = PrivacySafeUniverse(
        brief_id="2026-04-27",
        tickers=[UniverseTicker(ticker="NVDA", asset_class="us_equity")],
    )
    items = await adapter._fetch_finnhub(universe)

    assert len(items) == 1
    assert items[0].source_name == "Yahoo"
    assert items[0].fetched_via == "finnhub"
    # Redirector URL is preserved — that's still the only URL finnhub gave us.
    assert items[0].source_url == "https://finnhub.io/api/news?id=abc"


@pytest.mark.asyncio
async def test_finnhub_falls_back_to_finnhub_label_when_source_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If finnhub returned an article without the `source` field AND the
    URL is the finnhub redirector (so URL parsing yields nothing), the
    publisher label falls back to the aggregator name. Better honest
    than fabricating."""
    monkeypatch.setenv("FINNHUB_API_KEY", "test-token")

    class _FakeResponse:
        def json(self):
            return [
                {
                    "headline": "no source field",
                    "summary": "x",
                    "url": "https://finnhub.io/api/news?id=abc",
                    "datetime": int(datetime.now(UTC).timestamp()),
                }
            ]

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, _url, params=None):
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    adapter = NewsAdapter()
    universe = PrivacySafeUniverse(
        brief_id="2026-04-27",
        tickers=[UniverseTicker(ticker="NVDA", asset_class="us_equity")],
    )
    items = await adapter._fetch_finnhub(universe)

    assert items[0].source_name == "finnhub"
    assert items[0].fetched_via == "finnhub"


# ---------------------------------------------------------------------------
# runner._health_source_name with mixed publishers
# ---------------------------------------------------------------------------


def _adapter_stub():
    class A:
        source_name = "gdelt+google"

    return A()


def test_health_source_name_collapses_to_aggregator_when_publishers_vary() -> None:
    """After the publisher fix, items in one batch will have varying
    source_name (Yahoo, Reuters, MarketWatch...) — using source_name to
    label health would defeat the original intent ("this batch came via
    finnhub"). fetched_via preserves that signal."""
    items = [
        RawItem(
            source_name="Yahoo",
            source_tier="news",
            source_url="https://finance.yahoo.com/x",
            title="t1",
            excerpt="e1",
            fetched_at=datetime.now(UTC),
            fetched_via="finnhub",
        ),
        RawItem(
            source_name="MarketWatch",
            source_tier="news",
            source_url="https://www.marketwatch.com/x",
            title="t2",
            excerpt="e2",
            fetched_at=datetime.now(UTC),
            fetched_via="finnhub",
        ),
    ]
    assert _health_source_name(_adapter_stub(), items) == "finnhub"  # type: ignore[arg-type]


def test_health_source_name_preserves_legacy_source_name_path() -> None:
    """Adapters that haven't migrated to fetched_via (market / official)
    must keep the original source_name-based labelling intact."""
    items = [
        RawItem(
            source_name="stooq",
            source_tier="market",
            source_url="https://stooq.com/q/?s=nvda.us",
            title="quote",
            excerpt="quote",
            fetched_at=datetime.now(UTC),
        ),
    ]
    assert _health_source_name(_adapter_stub(), items) == "stooq"  # type: ignore[arg-type]


# Defensive: keep the existing fallback test contract intact.
def test_health_source_name_with_no_items_returns_adapter_name() -> None:
    assert _health_source_name(_adapter_stub(), []) == "gdelt+google"  # type: ignore[arg-type]


# Sanity: the existing fallback assertion in test_news_fallback shouldn't
# regress — that test uses synthesized items with source_name="finnhub" and
# no fetched_via, so it falls to the legacy path. We mirror it here for
# locality in case the file is renamed.
def test_synthetic_items_without_fetched_via_use_source_name() -> None:
    items = [
        RawItem(
            source_name="finnhub",
            source_tier="news",
            source_url="https://example.com/x",
            title="t",
            excerpt="e",
            detected_tickers=["NVDA"],
            published_at=datetime.now(UTC),
            fetched_at=datetime.now(UTC),
        )
    ]
    assert _health_source_name(_adapter_stub(), items) == "finnhub"  # type: ignore[arg-type]
