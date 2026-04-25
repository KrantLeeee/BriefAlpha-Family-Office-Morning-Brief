#!/usr/bin/env python
"""Seed the SQLite demo portfolio + watchlist.

Idempotent: re-running replaces the demo user's rows. Mirrors the 10
tickers from `apps/api/briefalpha_api/fixtures/brief.py` so the live
pipeline output matches the canvas-derived fixture proportions exactly.

Usage:
  cd apps/api && uv run python ../../scripts/seed_demo_portfolio.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Allow `python scripts/seed_demo_portfolio.py` from repo root or apps/api.
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
API_DIR = REPO_ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# Tests / dev typically don't have full secrets provisioned.
os.environ.setdefault("BRIEFALPHA_SKIP_SECRETS_CHECK", "1")

from sqlalchemy import delete  # noqa: E402

from briefalpha_api.db.models import Portfolio, Watchlist  # noqa: E402
from briefalpha_api.db.session import SessionLocal  # noqa: E402

DEMO_USER_ID = "demo"

# (ticker, weight, asset_class, sector) — must sum to 1.0 exactly.
PORTFOLIO_ROWS: list[tuple[str, float, str, str]] = [
    ("NVDA",    0.18, "us_equity",  "Information Technology"),
    ("0700.HK", 0.15, "hk_equity",  "Communication Services"),
    ("AAPL",    0.12, "us_equity",  "Information Technology"),
    ("MSFT",    0.10, "us_equity",  "Information Technology"),
    ("TLT",     0.10, "us_treasury", "Fixed Income"),
    ("9988.HK", 0.08, "hk_equity",  "Consumer Discretionary"),
    ("GLD",     0.08, "commodity",   "Commodities"),
    ("CASH",    0.09, "cash",        "Cash"),
    ("TSLA",    0.05, "us_equity",  "Consumer Discretionary"),
    ("MTN",     0.05, "us_equity",  "Consumer Discretionary"),
]

WATCHLIST: list[tuple[str, str]] = [
    ("AMD",     "us_equity"),
    ("GOOGL",   "us_equity"),
    ("1810.HK", "hk_equity"),
]


async def main() -> None:
    total_weight = round(sum(r[1] for r in PORTFOLIO_ROWS), 6)
    if total_weight != 1.0:
        raise SystemExit(
            f"PORTFOLIO_ROWS weights must sum to 1.0, got {total_weight}"
        )

    async with SessionLocal() as session:
        await session.execute(delete(Portfolio).where(Portfolio.user_id == DEMO_USER_ID))
        await session.execute(delete(Watchlist).where(Watchlist.user_id == DEMO_USER_ID))

        for ticker, weight, asset_class, sector in PORTFOLIO_ROWS:
            session.add(
                Portfolio(
                    user_id=DEMO_USER_ID,
                    ticker=ticker,
                    weight=weight,
                    asset_class=asset_class,
                    sector=sector,
                )
            )
        for ticker, asset_class in WATCHLIST:
            session.add(
                Watchlist(
                    user_id=DEMO_USER_ID, ticker=ticker, asset_class=asset_class
                )
            )

        await session.commit()

    print(
        f"[seed_demo_portfolio] wrote {len(PORTFOLIO_ROWS)} portfolio rows + "
        f"{len(WATCHLIST)} watchlist rows for user_id={DEMO_USER_ID}"
    )


if __name__ == "__main__":
    asyncio.run(main())
