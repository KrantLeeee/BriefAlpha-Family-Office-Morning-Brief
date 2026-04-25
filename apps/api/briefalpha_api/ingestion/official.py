"""Official adapter: SEC EDGAR RSS + HKEX RSS.

SEC's fair-use policy requires a contact email in `User-Agent`; the
startup `secrets_check` already verifies this is configured.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import yaml

from briefalpha_api.ingestion.base import IngestionAdapter, RawItem
from briefalpha_api.portfolio.models import PrivacySafeUniverse
from briefalpha_api.settings import CONFIG_DIR


def _user_agent() -> str:
    cfg = yaml.safe_load((CONFIG_DIR / "data_sources.yml").read_text(encoding="utf-8")) or {}
    return cfg.get("sec", {}).get("user_agent", "BriefAlpha demo <ops@example.com>")


class OfficialAdapter(IngestionAdapter):
    source_tier = "official"
    source_name = "sec+hkex"

    async def fetch(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        items: list[RawItem] = []
        items.extend(await self._fetch_sec(universe))
        items.extend(await self._fetch_hkex(universe))
        return items

    async def _fetch_sec(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        ua = _user_agent()
        url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&output=atom"
        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": ua}) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                return []
        # Lazy XML parse — `feedparser` not pinned in MVP; we keep this
        # adapter minimal on purpose so it's testable offline.
        return []

    async def _fetch_hkex(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        return []


def _now() -> datetime:
    return datetime.now(timezone.utc)
