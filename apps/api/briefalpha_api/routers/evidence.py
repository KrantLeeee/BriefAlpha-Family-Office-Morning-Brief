"""GET /api/evidence/trail — full evidence trail for a brief.

Demo mode returns the fixture's ``deep_read.evidence_trail`` (with each
row stamped ``source_tier="demo"`` so the drawer's filter chips work).
Live mode queries the ``evidence`` table for all rows associated with
the brief and orders newest-first by ``published_at``.

Response shape mirrors ``Brief.deep_read``::

    {
      "evidence_trail": [{ "timestamp": "...", "label": "...", "source_tier": "..." }],
      "evidence_total": int,
    }
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, select

from briefalpha_api.db.models import Evidence
from briefalpha_api.db.session import get_session
from briefalpha_api.fixtures.brief import get_demo_brief

router = APIRouter()


@router.get("/evidence/trail")
async def evidence_trail(
    request: Request,
    brief_id: str = Query(..., max_length=64),
    session=Depends(get_session),
) -> dict[str, Any]:
    mode = getattr(request.app.state, "mode", "live")

    if mode == "demo":
        fixture = get_demo_brief()
        return {
            "evidence_trail": [
                {**row, "source_tier": "demo"}
                for row in fixture["deep_read"]["evidence_trail"]
            ],
            "evidence_total": fixture["deep_read"]["evidence_total"],
        }

    rows = (
        await session.execute(
            select(Evidence)
            .where(Evidence.brief_id == brief_id)
            .order_by(desc(Evidence.published_at))
        )
    ).scalars().all()

    trail = [
        {
            "timestamp": row.published_at.isoformat() if row.published_at else "",
            "label": _format_label(row),
            "source_tier": row.source_tier,
        }
        for row in rows
    ]

    return {"evidence_trail": trail, "evidence_total": len(trail)}


def _format_label(ev: Evidence) -> str:
    """Compose a short human-readable label for the trail row.

    The Evidence model has no ``source_name`` column, so we fall back
    to ``source_tier`` as the prefix and append the (truncated) title.
    """
    name = ev.source_tier or ""
    title = (ev.title or "")[:40]
    if name and title:
        return f"{name} · {title}"
    return name or title
