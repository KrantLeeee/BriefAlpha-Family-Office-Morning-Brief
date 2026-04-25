"""Portfolio / watchlist repository (read-side)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from briefalpha_api.db.models import Portfolio as PortfolioRow
from briefalpha_api.db.models import Watchlist as WatchlistRow
from briefalpha_api.portfolio.models import PortfolioPosition
from briefalpha_api.portfolio.sector import resolve_asset_class


async def load_positions(session: AsyncSession, *, user_id: str) -> list[PortfolioPosition]:
    stmt = select(PortfolioRow).where(PortfolioRow.user_id == user_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        PortfolioPosition(
            ticker=r.ticker,
            weight=r.weight,
            asset_class=r.asset_class or resolve_asset_class(r.ticker),  # type: ignore[arg-type]
            sector=r.sector,
        )
        for r in rows
    ]


async def load_watchlist(session: AsyncSession, *, user_id: str) -> list[str]:
    stmt = select(WatchlistRow.ticker).where(WatchlistRow.user_id == user_id)
    return [r for r, in (await session.execute(stmt)).all()]
