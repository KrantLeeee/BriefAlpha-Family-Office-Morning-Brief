"""Ingestion orchestrator with source-level failure isolation.

Each adapter run records a `SourceHealthHistory` row so the 5-minute
aggregator and `/api/source-health` can show real status. Single-source
failures never abort the brief — they're surfaced as `degraded` / `failed`
status rows for the operator instead.
"""
from __future__ import annotations

import logging

from briefalpha_api.audit import record_source_health_async
from briefalpha_api.ingestion.base import IngestionAdapter, RawItem
from briefalpha_api.ingestion.market import MarketAdapter
from briefalpha_api.ingestion.news import NewsAdapter
from briefalpha_api.ingestion.official import OfficialAdapter
from briefalpha_api.portfolio.models import PrivacySafeUniverse

log = logging.getLogger("briefalpha.ingestion")


async def run_ingestion(universe: PrivacySafeUniverse) -> dict[str, list[RawItem]]:
    adapters: list[IngestionAdapter] = [
        MarketAdapter(),
        NewsAdapter(),
        OfficialAdapter(),
    ]
    out: dict[str, list[RawItem]] = {}
    for adapter in adapters:
        try:
            items = await adapter.fetch(universe)
            out[adapter.source_name] = items
            health_source_name = _health_source_name(adapter, items)
            await record_source_health_async(
                source_name=health_source_name,
                status="ok" if items else "degraded",
                detail=None if items else "no items returned",
                items_collected=len(items),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("ingestion failure for %s: %s", adapter.source_name, exc)
            out[adapter.source_name] = []
            await record_source_health_async(
                source_name=adapter.source_name,
                status="failed",
                detail=str(exc)[:240],
                items_collected=0,
            )
    return out


def _health_source_name(adapter: IngestionAdapter, items: list[RawItem]) -> str:
    """Prefer the concrete provider when a fallback returned all items.

    Reads `fetched_via` first because `source_name` was repurposed to mean
    *publisher* (Yahoo / Reuters / etc.) — that varies per article and
    would no longer collapse to a single value, defeating the original
    "label health by the actual aggregator that returned items" intent.
    Falls back to source_name for adapters that haven't migrated yet
    (market / official tiers still use source_name as identity)."""
    aggregators = {item.fetched_via for item in items if item.fetched_via}
    if len(aggregators) == 1:
        return next(iter(aggregators))
    item_sources = {item.source_name for item in items if item.source_name}
    if len(item_sources) == 1:
        return next(iter(item_sources))
    return adapter.source_name
