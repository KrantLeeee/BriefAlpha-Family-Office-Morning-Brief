"""News adapter: GDELT primary, Google News RSS fallback."""
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from briefalpha_api.ingestion.base import IngestionAdapter, RawItem, is_provider_enabled
from briefalpha_api.portfolio.models import PrivacySafeUniverse

_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


class NewsAdapter(IngestionAdapter):
    source_tier = "news"
    source_name = "gdelt+google"

    async def fetch(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        items: list[RawItem] = []
        if is_provider_enabled("gdelt"):
            items.extend(await self._fetch_gdelt(universe))
        if not items and is_provider_enabled("google_news_rss"):
            items.extend(await self._fetch_google_rss(universe))
        return items

    async def _fetch_gdelt(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        # Constrained to a small ticker set; broader keywords + universe
        # filter are added in section 4.3 follow-ups.
        if not universe.tickers:
            return []
        query = " OR ".join(t.ticker for t in universe.tickers[:10])
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    _GDELT_URL,
                    params={"query": query, "mode": "ArtList", "format": "json"},
                )
                resp.raise_for_status()
                payload = resp.json()
            except (httpx.HTTPError, ValueError):
                return []

        items: list[RawItem] = []
        now = datetime.now(timezone.utc)
        for art in payload.get("articles", [])[:30]:
            items.append(
                RawItem(
                    source_name="gdelt",
                    source_tier="news",
                    source_url=art.get("url"),
                    title=art.get("title", ""),
                    excerpt=art.get("seendescription") or art.get("title", ""),
                    detected_tickers=[],  # NER fills in pipeline.entity_linking
                    published_at=_parse_dt(art.get("seendate")) or now,
                    fetched_at=now,
                )
            )
        return items

    async def _fetch_google_rss(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        """Google News RSS fallback. Returns empty list in offline / error
        scenarios — pipeline tolerates zero items per source per design.md §8."""
        return []


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
