"""GET /api/portfolio (admin token gated, mode-aware).

  demo mode → fixture portfolio + watchlist (the entire purpose of demo)
  live mode → real `portfolio` / `watchlist` rows from the DB; empty arrays
              when the tables are empty (NEVER fixture).

The `is_demo` flag mirrors the source-health convention so the frontend
can label the source explicitly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from briefalpha_api.auth import require_admin_token
from briefalpha_api.db.models import Portfolio, Watchlist
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.fixtures.brief import get_demo_portfolio

router = APIRouter()
HKT = ZoneInfo("Asia/Hong_Kong")


def _now_hkt_label() -> str:
    return datetime.now(tz=HKT).strftime("%Y-%m-%d %H:%M")


async def _load_live_portfolio() -> dict[str, Any]:
    """Read real portfolio + watchlist rows from the DB.

    Returns the same response shape as the demo fixture so the frontend
    can render either uniformly. When the tables are empty we return
    blanks/empty arrays — never fixture content.
    """
    async with SessionLocal() as session:
        portfolio_rows = (
            await session.execute(select(Portfolio))
        ).scalars().all()
        watchlist_rows = (
            await session.execute(select(Watchlist))
        ).scalars().all()

    tiles: list[dict[str, Any]] = []
    total_weight = sum(p.weight for p in portfolio_rows) or 1.0
    for p in portfolio_rows:
        tiles.append(
            {
                "ticker": p.ticker,
                "weight_pct": f"{(p.weight / total_weight) * 100:.1f}%",
                # Quote / change wiring belongs to the brief pipeline; the
                # /api/portfolio surface only echoes weights + watchlist.
                "change_pct": "0.0%",
                "trend": "flat",
                "asset_class": p.asset_class,
            }
        )

    watchlist = [
        {"ticker": w.ticker, "asset_class": w.asset_class}
        for w in watchlist_rows
    ]

    if not tiles and not watchlist:
        return {"as_of_hkt": "", "tiles": [], "watchlist": []}

    return {
        "as_of_hkt": _now_hkt_label(),
        "tiles": tiles,
        "watchlist": watchlist,
    }


@router.get("/portfolio")
async def portfolio(
    request: Request,
    _token: str = Depends(require_admin_token),
) -> dict[str, Any]:
    mode = getattr(request.app.state, "mode", "live")
    if mode == "demo":
        body = get_demo_portfolio()
        body["is_demo"] = True
        return body

    body = await _load_live_portfolio()
    body["is_demo"] = False
    return body
