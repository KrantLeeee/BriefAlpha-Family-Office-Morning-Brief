"""GET /api/portfolio (admin token gated).

Returns the demo portfolio shape while we don't yet expose the full
portfolio editor — the body is the same as the brief's portfolio_snapshot
plus the admin's watchlist. Cross-checking the admin token at the gate
keeps the unredacted ticker list off public endpoints.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from briefalpha_api.auth import require_admin_token
from briefalpha_api.fixtures.brief import get_demo_portfolio

router = APIRouter()


@router.get("/portfolio")
async def portfolio(_token: str = Depends(require_admin_token)) -> dict[str, Any]:
    return get_demo_portfolio()
