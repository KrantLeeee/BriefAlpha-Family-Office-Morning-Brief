from __future__ import annotations

from datetime import UTC, datetime

from briefalpha_api.ingestion.base import RawItem
from briefalpha_api.ingestion.runner import _health_source_name


class _Adapter:
    source_name = "yfinance"


def test_health_source_name_uses_concrete_fallback_provider() -> None:
    item = RawItem(
        source_name="stooq",
        source_tier="market",
        source_url="https://stooq.com/q/?s=nvda.us",
        title="NVDA fallback quote",
        excerpt="quote",
        detected_tickers=["NVDA"],
        asset_class="us_equity",
        fetched_at=datetime.now(UTC),
    )

    assert _health_source_name(_Adapter(), [item]) == "stooq"  # type: ignore[arg-type]


def test_health_source_name_keeps_adapter_for_empty_or_mixed_items() -> None:
    assert _health_source_name(_Adapter(), []) == "yfinance"  # type: ignore[arg-type]
