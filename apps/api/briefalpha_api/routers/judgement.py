"""GET /api/judgement/{id}/drawer.

Returns the full drawer payload (reasoning_chain + evidences + suggested
questions). For now, slices it from the demo brief.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from briefalpha_api.fixtures.brief import get_demo_brief

router = APIRouter()


@router.get("/judgement/{judgement_id}/drawer")
async def judgement_drawer(judgement_id: str) -> dict[str, Any]:
    brief = get_demo_brief()
    for j in brief["judgements"]:
        if j["id"] == judgement_id:
            return {
                "brief_id": brief["brief_id"],
                "judgement": j,
            }
    raise HTTPException(status_code=404, detail={
        "error": {"code": "judgement_not_found", "message": f"No judgement {judgement_id}"}
    })
