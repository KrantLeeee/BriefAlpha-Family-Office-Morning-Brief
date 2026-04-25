"""GET /api/portfolio (authorized users only — admin token check stub)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from briefalpha_api.fixtures.brief import get_demo_portfolio

router = APIRouter()


@router.get("/portfolio")
async def portfolio() -> dict[str, Any]:
    return get_demo_portfolio()
