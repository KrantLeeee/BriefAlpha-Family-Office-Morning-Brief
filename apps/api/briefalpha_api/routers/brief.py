"""GET /api/brief/today.

Read path:
  redis brief:{date} HIT  → return as-is (live pipeline output)
  redis brief:{date} MISS → return fixture with stale=true and kick off
                            background generation; subsequent requests
                            see the live brief once it lands.

This keeps the route latency < 100ms regardless of pipeline state, and
ensures the UI is never blank — the worst case is "showing yesterday's
shape with stale chip".
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from briefalpha_api.cache import get_brief_cache, set_brief_cache
from briefalpha_api.fixtures.brief import get_demo_brief
from briefalpha_api.pipeline import run_full_brief

router = APIRouter()
log = logging.getLogger("briefalpha.routers.brief")

HKT = ZoneInfo("Asia/Hong_Kong")


def _today_hkt() -> str:
    return datetime.now(tz=HKT).strftime("%Y-%m-%d")


# Single-flight: once a brief is generating, additional GETs don't queue
# more workers. Use `asyncio.Lock` per brief_id; cleaned up after run.
_inflight: dict[str, asyncio.Task] = {}


def _spawn_generation(brief_id: str) -> None:
    if brief_id in _inflight and not _inflight[brief_id].done():
        return

    async def _run() -> None:
        try:
            log.info("background brief generation started for %s", brief_id)
            artifact = await run_full_brief(brief_id)
            await set_brief_cache(brief_id, artifact)
            log.info("background brief generation complete for %s", brief_id)
        except Exception as exc:  # noqa: BLE001
            log.exception("background brief generation failed for %s: %s", brief_id, exc)
        finally:
            _inflight.pop(brief_id, None)

    _inflight[brief_id] = asyncio.create_task(_run())


@router.get("/brief/today")
async def brief_today() -> dict[str, Any]:
    brief_id = _today_hkt()
    cached = await get_brief_cache(brief_id)
    if cached is not None:
        return cached

    # Cache miss — kick off generation in the background and serve fixture.
    _spawn_generation(brief_id)
    fixture = get_demo_brief()
    fixture["stale"] = True
    fixture["brief_id"] = brief_id
    fixture["brief_date_hkt"] = brief_id
    return fixture


@router.post("/admin/brief/regenerate")
async def regenerate() -> dict[str, str]:
    """Force-regenerate today's brief. Drops the cache and respawns."""
    brief_id = _today_hkt()
    _spawn_generation(brief_id)
    return {"status": "queued", "brief_id": brief_id}
