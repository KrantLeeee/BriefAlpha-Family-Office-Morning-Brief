"""Ingestion orchestrator with source-level failure isolation."""
from __future__ import annotations

import logging

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
        except Exception as exc:  # noqa: BLE001
            log.warning("ingestion failure for %s: %s", adapter.source_name, exc)
            out[adapter.source_name] = []
    return out
