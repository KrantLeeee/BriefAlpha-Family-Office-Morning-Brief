"""GET /api/judgement/{id}/drawer.

Reads today's cached brief from redis and serves the matching judgement
slice. Falls back to the demo fixture only if the cache is cold (so the
UI stays renderable on a fresh boot).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException

from briefalpha_api.cache import get_brief_cache
from briefalpha_api.fixtures.brief import get_demo_brief

router = APIRouter()
HKT = ZoneInfo("Asia/Hong_Kong")


def _today_hkt() -> str:
    return datetime.now(tz=HKT).strftime("%Y-%m-%d")


@router.get("/judgement/{judgement_id}/drawer")
async def judgement_drawer(judgement_id: str) -> dict[str, Any]:
    brief = await get_brief_cache(_today_hkt())
    if brief is None:
        brief = get_demo_brief()
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
