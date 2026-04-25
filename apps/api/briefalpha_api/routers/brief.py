"""GET /api/brief/today.

Cache-first, stale fallback (90s timeout) per design.md §8.

Until the live pipeline (sections 5/10) lands, this returns the demo fixture.
Once `pipeline.run_brief` writes to redis `brief:{date}`, this router will
read that value and only fall back to the fixture if redis is empty.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from briefalpha_api.fixtures.brief import get_demo_brief

router = APIRouter()


@router.get("/brief/today")
async def brief_today() -> dict[str, Any]:
    return get_demo_brief()
