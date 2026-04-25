"""Privacy-safe universe builder.

Implements design.md §4.5 / tasks 2.5–2.7:
- adds decoy tickers (sector representatives + broad-market ETFs) so each
  bucket has at least max(k, 5) members,
- enforces decoy ≤ holdings × 4 cap (else fall back to broad ETF only),
- emits `PrivacySafeUniverse` with **only** ticker + asset_class fields.
"""
from __future__ import annotations

from briefalpha_api.portfolio.bucket import build_buckets, detect_coarse_mode, fill_asset_class
from briefalpha_api.portfolio.models import (
    BucketSummary,
    PortfolioPosition,
    PrivacySafeUniverse,
    UniverseTicker,
)
from briefalpha_api.portfolio.sector import resolve_asset_class, resolve_sector
from briefalpha_api.settings import get_settings

# Sector representatives used as decoys when a real bucket only has the
# user's own holdings — keeps each bucket above k=3 without leaking weight
# or sector preference.
SECTOR_DECOYS: dict[str, list[str]] = {
    "Information Technology": ["AAPL", "MSFT", "NVDA", "AMD", "INTC"],
    "Communication Services": ["GOOGL", "META", "DIS"],
    "Tech & Comms": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"],
    "Consumer Discretionary": ["AMZN", "TSLA", "MTN"],
    "Financials": ["JPM", "BAC", "0005.HK", "0388.HK"],
    "Energy": ["XOM", "CVX"],
    "Health Care": ["PFE", "LLY"],
    "Consumer Staples": ["WMT", "PG", "KO"],
    "Fixed Income": ["TLT", "IEF"],
    "Commodities": ["GLD", "SLV"],
    "Broad Equity": ["SPY", "QQQ", "IWM", "2800.HK"],
}

BROAD_ETFS = ["SPY", "QQQ", "IWM", "2800.HK"]
MAX_DECOY_PER_HOLDING = 4
MIN_BUCKET_FILL = 5  # max(k=3, 5)


def _decoys_for(bucket_name: str, holdings: list[str], holdings_total: int) -> list[str]:
    pool = [t for t in SECTOR_DECOYS.get(bucket_name, []) if t not in holdings]
    cap = min(MAX_DECOY_PER_HOLDING * len(holdings), MIN_BUCKET_FILL - len(holdings))
    cap = max(cap, 0)
    if cap == 0:
        return []
    if len(pool) >= cap:
        return pool[:cap]
    # Fall back to broad ETFs if sector pool is too thin.
    extras = [t for t in BROAD_ETFS if t not in pool and t not in holdings]
    return (pool + extras)[:cap]


def build_universe(
    *,
    brief_id: str,
    positions: list[PortfolioPosition],
    watchlist: list[str],
) -> tuple[PrivacySafeUniverse, BucketSummary]:
    settings = get_settings()
    positions = [fill_asset_class(p) for p in positions]
    coarse = detect_coarse_mode(positions)
    summary = build_buckets(positions, coarse_mode=coarse)

    members: set[str] = set()
    for pos in positions:
        members.add(pos.ticker)
    for t in watchlist:
        members.add(t)

    holdings_total = len(positions)
    for bucket in summary.buckets:
        # Cap decoy ≤ holdings × 4 across all sectors; if we'd blow the cap,
        # only keep broad ETFs as the bucket's representatives.
        budget = MAX_DECOY_PER_HOLDING * holdings_total
        decoys = _decoys_for(bucket.name, bucket.members, holdings_total)
        if len(decoys) + len(bucket.members) > budget + len(bucket.members):
            decoys = [t for t in BROAD_ETFS if t not in bucket.members][:2]
        for t in decoys:
            members.add(t)

    if not summary.cold_start_passed:
        # Cold-start: ticker-level queries disabled — keep only the broad
        # market ETFs so ingestion still has *something* to fetch.
        members = set(BROAD_ETFS)

    universe_tickers = sorted(members)
    pu_tickers = [
        UniverseTicker(ticker=t, asset_class=resolve_asset_class(t))  # type: ignore[arg-type]
        for t in universe_tickers
    ]

    return (
        PrivacySafeUniverse(
            brief_id=brief_id,
            tickers=pu_tickers,
            coarse_bucket_mode=summary.coarse_bucket_mode,
            cold_start_passed=summary.cold_start_passed,
        ),
        summary,
    )
