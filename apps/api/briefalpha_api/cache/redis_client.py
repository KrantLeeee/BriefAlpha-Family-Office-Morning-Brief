"""Async Redis client with graceful degradation.

If the Redis server is unreachable (or returns an error), every helper
here logs a warning and returns the no-op result (`None` for getters,
`False` for setters). Routers must therefore treat redis as a *cache*,
not a primary store — they MUST always have a fallback path.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from redis import asyncio as redis_asyncio
from redis.exceptions import RedisError

from briefalpha_api.settings import get_settings

log = logging.getLogger("briefalpha.cache")

# brief:{YYYY-MM-DD} → JSON-encoded Brief artifact.
# TTL is 23 hours so the next 07:55 freeze always overwrites a stale entry
# before it expires. (Per design.md §8.)
BRIEF_TTL_SECONDS = 23 * 60 * 60

_client: dict[int, redis_asyncio.Redis] | redis_asyncio.Redis | None = None


def brief_key(brief_date_hkt: str) -> str:
    return f"brief:{brief_date_hkt}"


def get_redis() -> redis_asyncio.Redis | None:
    """Return a per-event-loop client or `None` if Redis can't be reached.

    Async redis clients are bound to the asyncio loop they were created in.
    Pytest spins up a fresh loop per test, so a globally-cached client
    blows up with "Event loop is closed" on the second test. We key the
    cache by the running loop's id; the GC reclaims old entries when the
    loop is destroyed and its references go away.

    Also honours `BRIEFALPHA_DISABLE_REDIS=1` so tests + offline dev can
    run without spawning a redis container.
    """
    if os.environ.get("BRIEFALPHA_DISABLE_REDIS") == "1":
        return None
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    loop_id = id(loop) if loop is not None else 0

    global _client
    if isinstance(_client, dict) and loop_id in _client:
        return _client[loop_id]
    if not isinstance(_client, dict):
        _client = {}

    try:
        client = redis_asyncio.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=2.0,
        )
        _client[loop_id] = client
        return client
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


async def invalidate_brief_cache(brief_id: str) -> None:
    """Drop the cached brief so the next GET re-runs the cache-miss flow.

    Thin wrapper around `delete_brief_cache` exposed as an
    invalidation-named helper for callers (e.g. the user-facing
    `/admin/data/refresh` endpoint) where "invalidate" reads more
    naturally than "delete". Behaves as a no-op when Redis is
    unavailable (in-memory / test mode).
    """
    await delete_brief_cache(brief_id)


# ---------------------------------------------------------------------------
# Generic JSON / list helpers (used by source_health cache, research queue,
# QA context, and admin diagnostics). All operations are best-effort and
# log + degrade rather than raising.
# ---------------------------------------------------------------------------


async def set_json(key: str, value: Any, *, ttl_seconds: int | None = None) -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        if ttl_seconds:
            await client.set(key, payload, ex=ttl_seconds)
        else:
            await client.set(key, payload)
        return True
    except RedisError as exc:
        log.warning("redis SET %s failed: %s", key, exc)
        return False


async def get_json(key: str) -> Any | None:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
    except RedisError as exc:
        log.warning("redis GET %s failed: %s", key, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("redis JSON decode failed for %s", key)
        return None


async def lpush(key: str, value: Any) -> bool:
    client = get_redis()
    if client is None:
        return False
    try:
        await client.lpush(key, json.dumps(value, ensure_ascii=False, default=str))
        return True
    except RedisError as exc:
        log.warning("redis LPUSH %s failed: %s", key, exc)
        return False


async def rpop(key: str) -> Any | None:
    client = get_redis()
    if client is None:
        return None
    try:
        raw = await client.rpop(key)
    except RedisError as exc:
        log.warning("redis RPOP %s failed: %s", key, exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def llen(key: str) -> int:
    client = get_redis()
    if client is None:
        return 0
    try:
        return int(await client.llen(key))
    except RedisError as exc:
        log.warning("redis LLEN %s failed: %s", key, exc)
        return 0


# Stable key constants used by the rest of the codebase.
SOURCE_HEALTH_KEY = "source_health:latest"
RESEARCH_QUEUE_KEY = "research:queue"
REANALYZE_QUEUE_KEY = "reanalyze:queue"


def qa_context_key(brief_id: str, scope: str, target_id: str | None) -> str:
    safe_target = target_id or "all"
    return f"qa:context:{brief_id}:{scope}:{safe_target}"
