"""POST /api/_analytics.

Receives the local frontend event batch and persists it to
`analytics_event` (and to `audit_log` for events that are part of the
audit-relevant set).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

router = APIRouter()

# In-memory buffer used until the live db wiring lands.
_BUFFER: list[dict[str, Any]] = []


@router.post("/_analytics")
async def analytics(payload: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = payload.get("events", [])
    for evt in events:
        evt.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        _BUFFER.append(evt)
    return {"received": len(events)}


@router.get("/_analytics/recent")
async def recent_analytics(limit: int = 50) -> dict[str, Any]:
    return {"events": _BUFFER[-limit:]}
