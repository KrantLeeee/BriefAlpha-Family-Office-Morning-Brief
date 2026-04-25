"""Unit tests for portfolio.universe (PRD §6.1)."""
from __future__ import annotations

from briefalpha_api.portfolio.models import PortfolioPosition
from briefalpha_api.portfolio.universe import build_universe


def _positions(rows: list[tuple[str, float, str]]) -> list[PortfolioPosition]:
    return [
        PortfolioPosition(ticker=t, weight=w, asset_class=ac)  # type: ignore[arg-type]
        for t, w, ac in rows
    ]


def test_30_ticker_universe_passes_k_anonymity() -> None:
    rows = [
        ("NVDA", 0.10, "us_equity"),
        ("AAPL", 0.10, "us_equity"),
        ("MSFT", 0.10, "us_equity"),
        ("AMD", 0.05, "us_equity"),
        ("INTC", 0.05, "us_equity"),
        ("0700.HK", 0.10, "hk_equity"),
        ("9988.HK", 0.05, "hk_equity"),
        ("3690.HK", 0.05, "hk_equity"),
        ("TLT", 0.10, "us_treasury"),
        ("IEF", 0.05, "us_treasury"),
        ("GLD", 0.05, "commodity"),
        ("SLV", 0.05, "commodity"),
    ]
    universe, summary = build_universe(
        brief_id="b1", positions=_positions(rows), watchlist=["AMD", "GOOGL"]
    )
    assert summary.cold_start_passed
    assert {b.name for b in summary.buckets}  # at least one bucket


def test_small_portfolio_falls_back_to_broad_etf() -> None:
    rows = [("NVDA", 0.5, "us_equity"), ("AAPL", 0.5, "us_equity")]
    universe, summary = build_universe(
        brief_id="b2", positions=_positions(rows), watchlist=[]
    )
    # 2 < k=3 means everything collapses to other_equity which is also < k →
    # cold_start_passed flips to False.
    assert summary.cold_start_passed is False
    # In that path universe is broad ETFs only (no real holdings exposed).
    tickers = universe.ticker_set()
    assert tickers.issubset({"SPY", "QQQ", "IWM", "2800.HK"})
