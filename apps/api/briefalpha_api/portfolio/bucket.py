"""Exposure bucket builder + k-anonymity gate."""
from __future__ import annotations

from collections import defaultdict

from briefalpha_api.portfolio.models import (
    BucketSummary,
    ExposureBucket,
    PortfolioPosition,
)
from briefalpha_api.portfolio.sector import resolve_asset_class, resolve_sector
from briefalpha_api.settings import get_settings


def _weight_band(weight: float) -> str:
    if weight >= 0.20:
        return "20%+"
    if weight >= 0.10:
        return "10-20%"
    if weight >= 0.05:
        return "5-10%"
    return "0-5%"


def build_buckets(
    positions: list[PortfolioPosition],
    *,
    coarse_mode: bool,
) -> BucketSummary:
    """Aggregate positions into sector buckets + apply k=3 merge.

    Per design.md §4.5, buckets with fewer than `k_anonymity_threshold`
    tickers are merged into `other_equity`; if that pool is also < k, the
    `cold_start_passed` flag flips to False so ticker-level queries are
    forbidden downstream.
    """
    settings = get_settings()
    k = settings.k_anonymity_threshold

    by_bucket: dict[str, list[PortfolioPosition]] = defaultdict(list)
    for pos in positions:
        sector = pos.sector or resolve_sector(pos.ticker)
        # In coarse mode collapse "Information Technology" / "Communication Services"
        # into a single "Tech & Comms" bucket so we get fewer, denser buckets.
        if coarse_mode and sector in {"Information Technology", "Communication Services"}:
            sector = "Tech & Comms"
        by_bucket[sector].append(pos)

    buckets: list[ExposureBucket] = []
    other_pool: list[PortfolioPosition] = []

    for sector, members in by_bucket.items():
        if len(members) < k:
            other_pool.extend(members)
            continue
        weight = sum(m.weight for m in members)
        buckets.append(
            ExposureBucket(
                name=sector,
                members=[m.ticker for m in members],
                weight_band=_weight_band(weight),
                coarse=coarse_mode,
            )
        )

    cold_start_passed = True
    diagnostics: list[str] = []

    if other_pool:
        if len(other_pool) >= k:
            buckets.append(
                ExposureBucket(
                    name="other_equity",
                    members=[m.ticker for m in other_pool],
                    weight_band=_weight_band(sum(m.weight for m in other_pool)),
                    coarse=coarse_mode,
                    is_other_equity_pool=True,
                )
            )
        else:
            cold_start_passed = False
            diagnostics.append(
                f"k-anonymity failed: other_equity pool has {len(other_pool)} < k={k}; "
                f"ticker-level queries disabled for this brief."
            )

    return BucketSummary(
        buckets=buckets,
        other_equity_members=[m.ticker for m in other_pool] if other_pool else [],
        coarse_bucket_mode=coarse_mode,
        cold_start_passed=cold_start_passed,
        diagnostics=diagnostics,
    )


def detect_coarse_mode(positions: list[PortfolioPosition]) -> bool:
    return len(positions) < get_settings().coarse_bucket_mode_threshold


def fill_asset_class(pos: PortfolioPosition) -> PortfolioPosition:
    """Best-effort fill of `asset_class` if missing."""
    if pos.asset_class:
        return pos
    return pos.model_copy(update={"asset_class": resolve_asset_class(pos.ticker)})
