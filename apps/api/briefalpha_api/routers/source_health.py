"""GET /api/source-health.

Read order:
  1. redis `source_health:latest` snapshot (5-minute aggregator output),
  2. on-the-fly aggregation from `source_health_history` (slower path),
  3. demo fixture (only when DB is empty — first-boot UX).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from briefalpha_api.audit import aggregate_source_health
from briefalpha_api.cache import SOURCE_HEALTH_KEY, get_json
from briefalpha_api.fixtures.brief import get_demo_source_health

router = APIRouter()


@router.get("/source-health")
async def source_health() -> dict[str, Any]:
    cached = await get_json(SOURCE_HEALTH_KEY)
    if cached:
        return cached

    # Cache miss — compute on the fly.
    snapshot = await aggregate_source_health()
    if snapshot.get("rows"):
        return snapshot

    # DB also empty (first boot, no ingestion run yet) — fixture so the UI
    # has something to render.
    return get_demo_source_health()
