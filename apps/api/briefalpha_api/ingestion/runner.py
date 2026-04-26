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
            await record_source_health_async(
                source_name=adapter.source_name,
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
