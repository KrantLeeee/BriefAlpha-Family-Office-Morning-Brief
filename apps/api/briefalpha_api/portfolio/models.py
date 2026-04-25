"""Portfolio domain types.

`PrivacySafeUniverse` is the *only* type ingestion adapters accept (per
design.md §4.5). Carries ticker + asset_class only — no weights, sectors,
or buckets that could leak portfolio shape downstream.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetClass = Literal[
    "us_equity",
    "us_equity_etf",
    "hk_equity",
    "hk_equity_etf",
    "us_treasury",
    "commodity",
    "cash",
]


class UniverseTicker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    asset_class: AssetClass


class PrivacySafeUniverse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brief_id: str
    tickers: list[UniverseTicker]
    coarse_bucket_mode: bool = False
    cold_start_passed: bool = True

    def ticker_set(self) -> set[str]:
        return {t.ticker for t in self.tickers}


class ExposureBucket(BaseModel):
    """A k-anonymized exposure bucket."""

    model_config = ConfigDict(extra="forbid")

    name: str
    members: list[str]  # tickers
    weight_band: str  # "0-5%" | "5-10%" | "10-20%" | "20%+"
    coarse: bool = False
    is_other_equity_pool: bool = False


class BucketSummary(BaseModel):
    """k-anonymity audit summary, attached to `universes.bucket_summary`."""

    model_config = ConfigDict(extra="forbid")

    buckets: list[ExposureBucket]
    other_equity_members: list[str] = Field(default_factory=list)
    coarse_bucket_mode: bool
    cold_start_passed: bool
    diagnostics: list[str] = Field(default_factory=list)


class PortfolioPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    weight: float
    asset_class: AssetClass
    sector: str | None = None
