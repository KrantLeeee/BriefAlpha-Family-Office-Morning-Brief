"""GET /api/source-health — mode-aware.

  demo mode → fixture (every row has is_demo: True)
  live mode → real aggregated snapshot (every row has is_demo: False);
              empty rows + status="error" if no ingestion has run.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

from briefalpha_api.audit import aggregate_source_health
from briefalpha_api.cache import SOURCE_HEALTH_KEY, get_json
from briefalpha_api.fixtures.brief import get_demo_source_health

router = APIRouter()
HKT = ZoneInfo("Asia/Hong_Kong")


@router.get("/source-health")
async def source_health(request: Request) -> dict[str, Any]:
    mode = getattr(request.app.state, "mode", "live")

    if mode == "demo":
        return get_demo_source_health()

    cached = await get_json(SOURCE_HEALTH_KEY)
    if cached:
        return _ensure_is_demo_false(cached)

    snapshot = await aggregate_source_health()
    rows = snapshot.get("rows") or []
    # The aggregator always synthesizes a "research" row even when no real
    # ingestion has occurred. Treat snapshots whose only row is that
    # placeholder as "empty" so the UI doesn't display a misleading row.
    real_rows = [r for r in rows if r.get("source_name") != "research"]
    if real_rows:
        return _ensure_is_demo_false(snapshot)

    # Live mode but DB is empty — return a clearly-not-fixture empty state.
    return {
        "as_of_hkt": datetime.now(tz=HKT).strftime("%H:%M"),
        "overall": "failed",
        "rows": [],
    }


def _ensure_is_demo_false(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Defensive: stamp `is_demo: False` on rows that lack the field
    (e.g. cached snapshots written before this field existed)."""
    for row in snapshot.get("rows", []):
        row.setdefault("is_demo", False)
    return snapshot
