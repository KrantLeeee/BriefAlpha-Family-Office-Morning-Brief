"""GET /api/source-health."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from briefalpha_api.fixtures.brief import get_demo_source_health

router = APIRouter()


@router.get("/source-health")
async def source_health() -> dict[str, Any]:
    return get_demo_source_health()
