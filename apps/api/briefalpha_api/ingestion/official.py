"""Official adapter: SEC EDGAR RSS + HKEX RSS.

SEC's fair-use policy requires a contact email in `User-Agent`; the
startup `secrets_check` already verifies this is configured.
"""
from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import datetime, timezone

import httpx
import yaml

from briefalpha_api.ingestion.base import IngestionAdapter, RawItem
from briefalpha_api.ingestion.symbol_map import cik_for, hkex_code_for
from briefalpha_api.portfolio.models import PrivacySafeUniverse
from briefalpha_api.settings import CONFIG_DIR

log = logging.getLogger("briefalpha.ingestion")

_SEC_EDGAR_URL = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&CIK={cik}&type=&dateb=&owner=include&count=10&output=atom"
)
_HKEX_RSS_URL = "https://www.hkexnews.hk/listedco/listconews/sehk/rss/{code}.xml"

# Per design: SEC fair-use ≤ 10 req/s.
_SEC_RATE_LIMIT_SECONDS = 0.1
_SEC_PER_TICKER_CAP = 5
_SEC_TOTAL_CAP = 50
_HKEX_PER_TICKER_CAP = 5
_HKEX_TOTAL_CAP = 30


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
        if not universe.tickers:
            return []
        try:
            import feedparser  # type: ignore[import-untyped]
        except ImportError as exc:
            log.warning("feedparser not installed; sec_edgar disabled: %s", exc)
            return []

        ua = _user_agent()
        items: list[RawItem] = []
        loop = asyncio.get_running_loop()

        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": ua, "Accept": "application/atom+xml"},
        ) as client:
            for tk in universe.tickers:
                if len(items) >= _SEC_TOTAL_CAP:
                    break
                cik = cik_for(tk.ticker)
                if not cik:
                    log.warning("sec_edgar: no CIK for ticker %s; skipping", tk.ticker)
                    continue

                url = _SEC_EDGAR_URL.format(cik=cik)
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    body = resp.text
                except httpx.HTTPError as exc:
                    log.warning("sec_edgar fetch failed for %s (CIK %s): %s", tk.ticker, cik, exc)
                    await asyncio.sleep(_SEC_RATE_LIMIT_SECONDS)
                    continue

                try:
                    parsed = await loop.run_in_executor(None, feedparser.parse, body)
                except Exception as exc:  # noqa: BLE001
                    log.warning("sec_edgar parse failed for %s: %s", tk.ticker, exc)
                    await asyncio.sleep(_SEC_RATE_LIMIT_SECONDS)
                    continue

                entries = getattr(parsed, "entries", []) or []
                added = 0
                for entry in entries:
                    if added >= _SEC_PER_TICKER_CAP or len(items) >= _SEC_TOTAL_CAP:
                        break
                    item = _entry_to_raw_item(
                        entry,
                        source_name="sec_edgar",
                        asset_class=tk.asset_class,
                    )
                    if item is not None:
                        items.append(item)
                        added += 1

                # Rate-limit between ticker fetches (≤ 10 req/s).
                await asyncio.sleep(_SEC_RATE_LIMIT_SECONDS)
        return items

    async def _fetch_hkex(self, universe: PrivacySafeUniverse) -> list[RawItem]:
        if not universe.tickers:
            return []
        try:
            import feedparser  # type: ignore[import-untyped]
        except ImportError as exc:
            log.warning("feedparser not installed; hkex disabled: %s", exc)
            return []

        items: list[RawItem] = []
        loop = asyncio.get_running_loop()

        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"Accept": "application/rss+xml,application/xml"},
        ) as client:
            for tk in universe.tickers:
                if len(items) >= _HKEX_TOTAL_CAP:
                    break
                if not tk.ticker.endswith(".HK"):
                    continue
                code = hkex_code_for(tk.ticker)
                if not code:
                    log.warning("hkex: no stock code for ticker %s; skipping", tk.ticker)
                    continue

                url = _HKEX_RSS_URL.format(code=code)
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    body = resp.text
                except httpx.HTTPError as exc:
                    log.warning("hkex fetch failed for %s (%s): %s", tk.ticker, code, exc)
                    continue

                try:
                    parsed = await loop.run_in_executor(None, feedparser.parse, body)
                except Exception as exc:  # noqa: BLE001
                    log.warning("hkex parse failed for %s: %s", tk.ticker, exc)
                    continue

                entries = getattr(parsed, "entries", []) or []
                added = 0
                for entry in entries:
                    if added >= _HKEX_PER_TICKER_CAP or len(items) >= _HKEX_TOTAL_CAP:
                        break
                    item = _entry_to_raw_item(
                        entry,
                        source_name="hkex",
                        asset_class=tk.asset_class,
                    )
                    if item is not None:
                        items.append(item)
                        added += 1
        return items


def _entry_get(entry, key: str, default=None):
    """feedparser entries are sometimes dicts, sometimes FeedParserDict."""
    if isinstance(entry, dict):
        return entry.get(key, default)
    return getattr(entry, key, default)


def _entry_to_raw_item(entry, *, source_name: str, asset_class: str | None) -> RawItem | None:
    """Convert a feedparser entry into a RawItem; return None on parse failure."""
    try:
        title = _entry_get(entry, "title", "") or ""
        link = _entry_get(entry, "link", None)
        summary = (_entry_get(entry, "summary", None) or title or "")
        excerpt = summary[:400]
        # Atom feeds expose `updated_parsed`; RSS uses `published_parsed`.
        struct_time = (
            _entry_get(entry, "published_parsed", None)
            or _entry_get(entry, "updated_parsed", None)
        )
        published_at = _struct_to_dt(struct_time)
        return RawItem(
            source_name=source_name,
            source_tier="official",
            source_url=link,
            title=title or "",
            excerpt=excerpt,
            detected_tickers=[],
            asset_class=asset_class,
            published_at=published_at,
            fetched_at=_now(),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("%s entry parse failed: %s", source_name, exc)
        return None


def _struct_to_dt(struct_time) -> datetime | None:
    if not struct_time:
        return None
    try:
        epoch = calendar.timegm(struct_time)
        return datetime.fromtimestamp(epoch, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)
