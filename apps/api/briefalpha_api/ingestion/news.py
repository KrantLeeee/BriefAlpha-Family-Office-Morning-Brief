"""News adapter: GDELT primary, Google News RSS fallback."""
from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx

from briefalpha_api.ingestion.base import IngestionAdapter, RawItem, is_provider_enabled
from briefalpha_api.portfolio.models import PrivacySafeUniverse

log = logging.getLogger("briefalpha.ingestion")

_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)


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
            except (httpx.HTTPError, ValueError) as exc:
                log.warning("gdelt fetch failed: %s", exc)
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
        if not universe.tickers:
            return []

        # Up to 10 tickers OR-joined; URL-encode the whole query string.
        query = " OR ".join(t.ticker for t in universe.tickers[:10])
        url = _GOOGLE_NEWS_RSS.format(query=quote_plus(query))

        try:
            import feedparser  # type: ignore[import-untyped]
        except ImportError as exc:
            log.warning("feedparser not installed; google_news_rss disabled: %s", exc)
            return []

        try:
            loop = asyncio.get_running_loop()
            parsed = await loop.run_in_executor(None, feedparser.parse, url)
        except (httpx.HTTPError, Exception) as exc:  # noqa: BLE001
            log.warning("google_news_rss fetch failed: %s", exc)
            return []

        items: list[RawItem] = []
        now = datetime.now(timezone.utc)
        entries = getattr(parsed, "entries", []) or []
        for entry in entries[:30]:
            try:
                title = _entry_get(entry, "title", "") or ""
                link = _entry_get(entry, "link", None)
                summary = _entry_get(entry, "summary", None) or title
                excerpt = (summary or "")[:400]
                published_at = _struct_to_dt(
                    _entry_get(entry, "published_parsed", None)
                )
                items.append(
                    RawItem(
                        source_name="google_news_rss",
                        source_tier="news",
                        source_url=link,
                        title=title or "",
                        excerpt=excerpt,
                        detected_tickers=[],
                        published_at=published_at,
                        fetched_at=now,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("google_news_rss entry parse failed: %s", exc)
                continue
        return items


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _entry_get(entry, key: str, default):
    """feedparser entries are sometimes dicts, sometimes FeedParserDict."""
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _struct_to_dt(struct_time) -> datetime | None:
    """Convert a feedparser `published_parsed` struct_time → UTC datetime."""
    if not struct_time:
        return None
    try:
        # `published_parsed` from feedparser is a UTC time.struct_time;
        # calendar.timegm is the inverse of gmtime (UTC → epoch).
        epoch = calendar.timegm(struct_time)
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None
