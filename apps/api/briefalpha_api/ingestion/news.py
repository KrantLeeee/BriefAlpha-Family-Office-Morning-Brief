"""News adapter: GDELT primary, Google News RSS fallback."""
from __future__ import annotations

import asyncio
import calendar
import logging
import os
from datetime import UTC, datetime
from datetime import timedelta
from urllib.parse import quote_plus

import httpx

from briefalpha_api.ingestion.base import IngestionAdapter, RawItem, is_provider_enabled
from briefalpha_api.portfolio.models import PrivacySafeUniverse

log = logging.getLogger("briefalpha.ingestion")

_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_FINNHUB_COMPANY_NEWS_URL = "https://finnhub.io/api/v1/company-news"
_NEWSAPI_EVERYTHING_URL = "https://newsapi.org/v2/everything"
_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)
_GDELT_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_KEYED_TIMEOUT = httpx.Timeout(8.0, connect=3.0)
_RSS_TIMEOUT = httpx.Timeout(8.0, connect=3.0)


class NewsAdapter(IngestionAdapter):
    source_tier = "news"
    source_name = "gdelt+google"

    async def fetch(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        items: list[RawItem] = []
        if is_provider_enabled("gdelt"):
            items.extend(await self._fetch_gdelt(universe))
        if not items and is_provider_enabled("finnhub"):
            items.extend(await self._fetch_finnhub(universe))
        if not items and is_provider_enabled("newsapi"):
            items.extend(await self._fetch_newsapi(universe))
        if not items and is_provider_enabled("google_news_rss"):
            items.extend(await self._fetch_google_rss(universe))
        return items

    async def _fetch_gdelt(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        # Constrained to a small ticker set; broader keywords + universe
        # filter are added in section 4.3 follow-ups.
        if not universe.tickers:
            return []
        query = " OR ".join(t.ticker for t in universe.tickers[:10])
        async with httpx.AsyncClient(timeout=_GDELT_TIMEOUT) as client:
            try:
                resp = await client.get(
                    _GDELT_URL,
                    params={"query": query, "mode": "ArtList", "format": "json"},
                )
                resp.raise_for_status()
                payload = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                # `ConnectTimeout('')` has empty repr; spell out host + the
                # actually-resolved IP so a sinkhole/poisoning shows up in
                # the log instead of looking like a generic outage.
                log.warning(
                    "gdelt fetch failed (%s host=%s ip=%s): %s",
                    type(exc).__name__,
                    httpx.URL(_GDELT_URL).host,
                    _resolve_ip_for_log(httpx.URL(_GDELT_URL).host),
                    exc,
                )
                return []

        items: list[RawItem] = []
        now = datetime.now(UTC)
        for art in payload.get("articles", [])[:30]:
            url = art.get("url")
            publisher = (
                art.get("domain")
                or _publisher_from_url(url)
                or "gdelt"
            )
            items.append(
                RawItem(
                    source_name=publisher,
                    source_tier="news",
                    source_url=url,
                    title=art.get("title", ""),
                    excerpt=art.get("seendescription") or art.get("title", ""),
                    detected_tickers=[],  # NER fills in pipeline.entity_linking
                    published_at=_parse_dt(art.get("seendate")) or now,
                    fetched_at=now,
                    fetched_via="gdelt",
                )
            )
        return items

    async def _fetch_finnhub(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        token = os.environ.get("FINNHUB_API_KEY", "").strip()
        if not token:
            return []
        symbols = [t.ticker for t in universe.tickers[:10] if "." not in t.ticker]
        if not symbols:
            return []

        now = datetime.now(UTC)
        date_to = now.date()
        date_from = date_to - timedelta(days=7)
        items: list[RawItem] = []
        async with httpx.AsyncClient(timeout=_KEYED_TIMEOUT) as client:
            for symbol in symbols:
                if len(items) >= 30:
                    break
                try:
                    resp = await client.get(
                        _FINNHUB_COMPANY_NEWS_URL,
                        params={
                            "symbol": symbol,
                            "from": date_from.isoformat(),
                            "to": date_to.isoformat(),
                            "token": token,
                        },
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                except (httpx.HTTPError, ValueError) as exc:
                    log.warning("finnhub news fetch failed for %s: %r", symbol, exc)
                    continue
                if not isinstance(payload, list):
                    continue
                for art in payload:
                    if len(items) >= 30:
                        break
                    title = art.get("headline") or ""
                    if not title:
                        continue
                    published_at = _unix_to_dt(art.get("datetime")) or now
                    url = art.get("url")
                    # Finnhub returns a redirector URL of the form
                    # `https://finnhub.io/api/news?id=...` which 302s to the
                    # real publisher. Prefer the API's own `source` field
                    # (e.g. "Yahoo", "MarketWatch") so the user sees the
                    # publisher rather than the aggregator.
                    publisher = (
                        (art.get("source") or "").strip()
                        or _publisher_from_url(url)
                        or "finnhub"
                    )
                    items.append(
                        RawItem(
                            source_name=publisher,
                            source_tier="news",
                            source_url=url,
                            title=title,
                            excerpt=art.get("summary") or title,
                            detected_tickers=[symbol],
                            published_at=published_at,
                            fetched_at=now,
                            fetched_via="finnhub",
                        )
                    )
        return items

    async def _fetch_newsapi(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        token = os.environ.get("NEWSAPI_KEY", "").strip()
        if not token or not universe.tickers:
            return []

        query = " OR ".join(t.ticker for t in universe.tickers[:10])
        now = datetime.now(UTC)
        try:
            async with httpx.AsyncClient(timeout=_KEYED_TIMEOUT) as client:
                resp = await client.get(
                    _NEWSAPI_EVERYTHING_URL,
                    params={
                        "q": query,
                        "language": "en",
                        "sortBy": "publishedAt",
                        "pageSize": 30,
                        "apiKey": token,
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("newsapi fetch failed: %r", exc)
            return []

        items: list[RawItem] = []
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        for art in articles[:30]:
            title = art.get("title") or ""
            if not title:
                continue
            url = art.get("url")
            source_obj = art.get("source") or {}
            publisher = (
                (source_obj.get("name") if isinstance(source_obj, dict) else "")
                or _publisher_from_url(url)
                or "newsapi"
            )
            items.append(
                RawItem(
                    source_name=publisher,
                    source_tier="news",
                    source_url=url,
                    title=title,
                    excerpt=art.get("description") or title,
                    detected_tickers=[],
                    published_at=_parse_iso_dt(art.get("publishedAt")) or now,
                    fetched_at=now,
                    fetched_via="newsapi",
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
            async with httpx.AsyncClient(timeout=_RSS_TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            loop = asyncio.get_running_loop()
            parsed = await loop.run_in_executor(None, feedparser.parse, resp.content)
        except (httpx.HTTPError, Exception) as exc:  # noqa: BLE001
            log.warning("google_news_rss fetch failed: %s", exc)
            return []

        items: list[RawItem] = []
        now = datetime.now(UTC)
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
                # Google News RSS entries expose the original publisher in
                # an inner `source` element (parsed by feedparser as either
                # a dict-like or string). The `link` field is a Google
                # redirector — host parsing would yield "news.google.com",
                # which `_publisher_from_url` rejects as an aggregator.
                publisher = (
                    _google_rss_publisher(entry)
                    or _publisher_from_url(link)
                    or "google_news_rss"
                )
                items.append(
                    RawItem(
                        source_name=publisher,
                        source_tier="news",
                        source_url=link,
                        title=title or "",
                        excerpt=excerpt,
                        detected_tickers=[],
                        published_at=published_at,
                        fetched_at=now,
                        fetched_via="google_news_rss",
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
        return datetime.strptime(raw, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _parse_iso_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _unix_to_dt(raw) -> datetime | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


def _resolve_ip_for_log(host: str) -> str:
    """Best-effort A-record lookup for log diagnostics. Never raises."""
    try:
        import socket

        return socket.gethostbyname(host)
    except (OSError, ValueError):
        return "unresolved"


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
        return datetime.fromtimestamp(epoch, tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


# Hosts that mean "we couldn't resolve the real publisher" — they're
# aggregator/redirector domains, so falling back to them as a publisher
# label would put us right back where we started.
_AGGREGATOR_HOSTS = {
    "finnhub.io",
    "news.google.com",
    "google.com",
    "www.google.com",
}


def _google_rss_publisher(entry) -> str | None:
    """Pull the original publisher name out of a Google News RSS entry.

    feedparser parses the inner `<source url="…">Reuters</source>` element
    as either a dict-like with a `title` key or a string, depending on
    feedparser version. We try both shapes; missing-data returns None so
    the caller can fall back to the URL-host parser."""
    src = _entry_get(entry, "source", None)
    if isinstance(src, str) and src.strip():
        return src.strip()
    if isinstance(src, dict):
        title = src.get("title") or src.get("href") or ""
        if isinstance(title, str) and title.strip():
            return title.strip()
    # Some feedparser versions surface it as `entry.source.title`.
    title_attr = getattr(src, "title", None)
    if isinstance(title_attr, str) and title_attr.strip():
        return title_attr.strip()
    return None


def _publisher_from_url(url: str | None) -> str | None:
    """Extract a clean publisher hostname from a URL, e.g.
    `https://finance.yahoo.com/news/...` → `finance.yahoo.com`. Strips a
    leading `www.` and returns None for aggregator/redirector domains
    (their host tells the user nothing about the original article)."""
    if not url:
        return None
    try:
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower()
    except (ValueError, TypeError):
        return None
    if not host:
        return None
    if host in _AGGREGATOR_HOSTS:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None
