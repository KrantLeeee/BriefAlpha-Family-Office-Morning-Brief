"""Async Redis client with graceful degradation.

If the Redis server is unreachable (or returns an error), every helper
here logs a warning and returns the no-op result (`None` for getters,
`False` for setters). Routers must therefore treat redis as a *cache*,
not a primary store — they MUST always have a fallback path.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from redis import asyncio as redis_asyncio
from redis.exceptions import RedisError

from briefalpha_api.settings import get_settings

log = logging.getLogger("briefalpha.cache")

# brief:{YYYY-MM-DD} → JSON-encoded Brief artifact.
# TTL is 23 hours so the next 07:55 freeze always overwrites a stale entry
# before it expires. (Per design.md §8.)
BRIEF_TTL_SECONDS = 23 * 60 * 60

_client: redis_asyncio.Redis | None = None


def brief_key(brief_date_hkt: str) -> str:
    return f"brief:{brief_date_hkt}"


def get_redis() -> redis_asyncio.Redis | None:
    """Return a singleton client or `None` if Redis can't be reached.

    The first failure logs once and caches `None` — we don't want every
    request to attempt a TCP connect when redis is offline. A successful
    later call (e.g., after redis comes back) requires `reset_redis()`.
    """
    global _client
    if _client is not None:
        return _client
    try:
        _client = redis_asyncio.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=2.0,
        )
        return _client
    except RedisError as exc:  # pragma: no cover — connection-time only
        log.warning("redis init failed: %s — falling back to no-cache mode", exc)
        return None


def reset_redis() -> None:
    """Close + clear the singleton (used in tests)."""
    global _client
    _client = None


async def get_brief_cache(brief_date_hkt: str) -> dict[str, Any] | None:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(brief_key(brief_date_hkt))
    except RedisError as exc:
        log.warning("redis GET failed: %s", exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("redis returned invalid JSON for %s: %s", brief_date_hkt, exc)
        return None


async def set_brief_cache(brief_date_hkt: str, payload: dict[str, Any]) -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        await client.set(
            brief_key(brief_date_hkt),
            json.dumps(payload, ensure_ascii=False, default=str),
            ex=BRIEF_TTL_SECONDS,
        )
        return True
    except RedisError as exc:
        log.warning("redis SET failed: %s", exc)
        return False


async def delete_brief_cache(brief_date_hkt: str) -> None:
    client = get_redis()
    if client is None:
        return
    try:
        await client.delete(brief_key(brief_date_hkt))
    except RedisError as exc:
        log.warning("redis DEL failed: %s", exc)
