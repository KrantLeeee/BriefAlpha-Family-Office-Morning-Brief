"""GET /api/judgement/{id}/drawer (mode-aware).

  HIT, demo  → serve from cache
  HIT, live  → serve from cache
  MISS, demo → fall back to demo fixture (demo IS fixture)
  MISS, live → return an empty drawer skeleton; NEVER fixture content.

The fixture-fallback path matters: cache cold-starts immediately after
ingestion (before brief generation completes) are normal operation and
must not leak the demo brief into live deployments.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request

from briefalpha_api.cache import get_brief_cache
from briefalpha_api.fixtures.brief import get_demo_brief

router = APIRouter()
HKT = ZoneInfo("Asia/Hong_Kong")


def _today_hkt() -> str:
    return datetime.now(tz=HKT).strftime("%Y-%m-%d")


def _empty_drawer(brief_id: str, judgement_id: str) -> dict[str, Any]:
    """Live mode skeleton: matches the shape the frontend reads off the
    drawer slice but with empty arrays / blanks."""
    return {
        "brief_id": brief_id,
        "judgement": {
            "id": judgement_id,
            "rank": 0,
            "level": "info",
            "level_label": "",
            "title": "",
            "metadata": "",
            "evidence_count": 0,
            "requires_review": False,
            "review": None,
            "no_direct_portfolio_link": False,
            "reasoning_chain": {},
            "evidence": [],
            "supplementary_sources": [],
            "suggested_questions": [],
        },
    }


@router.get("/judgement/{judgement_id}/drawer")
async def judgement_drawer(judgement_id: str, request: Request) -> dict[str, Any]:
    # Default to "live" if state.mode is unset — never accidentally serve
    # fixture in unknown contexts.
    mode = getattr(request.app.state, "mode", "live")
    brief_id = _today_hkt()
    brief = await get_brief_cache(brief_id)

    if brief is None:
        if mode == "demo":
            brief = get_demo_brief()
        else:
            # live + cache miss: empty skeleton, NEVER fixture
            return _empty_drawer(brief_id, judgement_id)

    for j in brief["judgements"]:
        if j["id"] == judgement_id:
            return {
                "brief_id": brief["brief_id"],
                "judgement": j,
            }
    raise HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "judgement_not_found",
                "message": f"No judgement {judgement_id}",
            }
        },
    )
