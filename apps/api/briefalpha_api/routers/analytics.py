"""POST /api/_analytics.

Receives the local frontend event batch and persists it to
`analytics_event`. Events whose names appear in `AUDIT_RELEVANT_EVENTS`
are also appended to `audit_log` so admin diagnostics has one canonical
view of the things that matter for compliance.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from briefalpha_api.audit import AuditRecord, record_audit
from briefalpha_api.db.models import AnalyticsEvent
from briefalpha_api.db.session import get_session

router = APIRouter()
log = logging.getLogger("briefalpha.routers.analytics")

# Names mirror PRD §5.3.
AUDIT_RELEVANT_EVENTS = {
    "qa_response_render",
    "drawer_close",
    "conservative_brief_rendered",
    "consent_state_changed",
    "audit_mode_toggle",
}


@router.post("/_analytics")
async def analytics(payload: dict[str, Any], session=Depends(get_session)) -> dict[str, Any]:
    events: list[dict[str, Any]] = payload.get("events", [])
    written = 0
    for evt in events:
        name = evt.get("event_name") or evt.get("name") or "unknown"
        body = evt.get("payload") or {k: v for k, v in evt.items() if k not in {"event_name", "name"}}
        session.add(
            AnalyticsEvent(
                event_name=name,
                payload=body,
                user_id=evt.get("user_id"),
                brief_id=evt.get("brief_id"),
                recorded_at=datetime.now(timezone.utc),
            )
        )
        if name in AUDIT_RELEVANT_EVENTS:
            await record_audit(
                session,
                AuditRecord(
                    request_hash=_hash(body),
                    response_hash=None,
                    scope=f"analytics:{name}",
                    cited_evidence_ids=[],
                    accuracy_validation_passed=body.get("validation_passed"),
                    call_type="analytics",
                    provider=None,
                    model=None,
                    template_version=None,
                    latency_ms=body.get("duration_ms"),
                    failure_state=None,
                    audit_mode="demo",
                    brief_id=evt.get("brief_id"),
                ),
            )
        written += 1
    await session.commit()
    return {"received": written}


@router.get("/_analytics/recent")
async def recent_analytics(limit: int = 50, session=Depends(get_session)) -> dict[str, Any]:
    stmt = (
        select(AnalyticsEvent)
        .order_by(AnalyticsEvent.recorded_at.desc())
        .limit(min(limit, 200))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {
        "events": [
            {
                "id": r.id,
                "event_name": r.event_name,
                "payload": r.payload,
                "user_id": r.user_id,
                "brief_id": r.brief_id,
                "recorded_at": r.recorded_at.isoformat(),
            }
            for r in rows
        ]
    }


def _hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
