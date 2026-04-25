"""Adapter ABC + RawItem schema."""
from __future__ import annotations

import abc
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from briefalpha_api.portfolio.models import PrivacySafeUniverse
from briefalpha_api.settings import CONFIG_DIR

SourceTier = Literal["market", "news", "official", "research"]


class RawItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_tier: SourceTier
    source_url: str | None = None
    title: str
    excerpt: str
    quote_span: tuple[int, int] | None = None
    detected_tickers: list[str] = []
    asset_class: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    raw_payload_hash: str | None = None


class IngestionAdapter(abc.ABC):
    source_tier: SourceTier
    source_name: str

    @abc.abstractmethod
    async def fetch(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        ...


@lru_cache(maxsize=1)
def load_data_sources_config() -> dict:
    path: Path = CONFIG_DIR / "data_sources.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def is_provider_enabled(name: str) -> bool:
    cfg = load_data_sources_config()
    return cfg.get("providers", {}).get(name, {}).get("enabled", False)
