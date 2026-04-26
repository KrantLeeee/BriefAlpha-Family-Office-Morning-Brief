"""GET /api/brief/today.

Read path (mode-aware):
  HIT, demo  → stamp system={mode:demo, status:ready, data_quality:fixture}
  HIT, live  → stamp system={mode:live, status:ready, data_quality:live}
  MISS, demo → serve fixture + stamp system={mode:demo, status:ready, data_quality:fixture}; spawn generation
  MISS, live → return empty skeleton + stamp system={mode:live, status:generating, data_quality:unavailable}; spawn generation

Live mode NEVER returns the fixture. Demo mode is the explicit, opt-in
surface for the bundled fixture content.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

from briefalpha_api.cache import get_brief_cache, set_brief_cache
from briefalpha_api.fixtures.brief import get_demo_brief
from briefalpha_api.pipeline.run import run_full_brief

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


def _now_iso_hkt() -> str:
    return datetime.now(tz=HKT).isoformat(timespec="seconds")


def _stamp_system(
    brief: dict[str, Any],
    *,
    mode: str,
    status: str,
    data_quality: str,
) -> dict[str, Any]:
    """Set the `system` envelope on the response.

    `generated_at` is preserved if already present (set by the pipeline
    when the artifact lands); `last_refreshed_at` is always now-HKT so
    the UI can show "freshly served".
    """
    existing = brief.get("system") or {}
    brief["system"] = {
        "mode": mode,
        "status": status,
        "generated_at": existing.get("generated_at"),
        "last_refreshed_at": _now_iso_hkt(),
        "data_quality": data_quality,
    }
    return brief


def _empty_brief_skeleton(brief_id: str) -> dict[str, Any]:
    """Minimal Brief shape returned in live mode while generation is in flight.

    All arrays are empty and string fields are blanks; the frontend should
    rely on `system.status == 'generating'` to show a loading state rather
    than render zeros as real data.
    """
    return {
        "brief_id": brief_id,
        "brief_date_hkt": brief_id,
        "delivered_at_hkt": "",
        "freeze_window_hkt": "",
        "stale": False,
        "audit_mode": "compliance",
        "anonymized": True,
        "no_direct_portfolio_link": False,
        "conservative": False,
        "degraded_sources": [],
        "base_case": {
            "headline_label": "",
            "headline": "",
            "summary": "",
            "estimate_label": "",
            "estimate_value": "",
            "estimate_direction": "flat",
            "estimate_explainer": "",
            "evidence_count": 0,
        },
        "portfolio_snapshot": {"as_of_hkt": "", "tiles": [], "watchlist_summary": ""},
        "judgements": [],
        "playbook_events": [],
        "deep_read": {"evidence_trail": [], "evidence_total": 0},
        "macro_pulse_collapsed": {"label": "", "expand_label": ""},
        "macro_pulse": [],
        "footer": {"left": "", "right": ""},
    }


@router.get("/brief/today")
async def brief_today(request: Request) -> dict[str, Any]:
    brief_id = _today_hkt()
    mode = request.app.state.mode  # "demo" | "live", set by lifespan
    cached = await get_brief_cache(brief_id)

    if cached is not None:
        data_quality = "live" if mode == "live" else "fixture"
        return _stamp_system(cached, mode=mode, status="ready", data_quality=data_quality)

    if mode == "demo":
        _spawn_generation(brief_id)
        fixture = get_demo_brief()
        fixture["brief_id"] = brief_id
        fixture["brief_date_hkt"] = brief_id
        return _stamp_system(fixture, mode="demo", status="ready", data_quality="fixture")

    # live + cache miss: kick off generation, return skeleton (NEVER fixture)
    _spawn_generation(brief_id)
    skeleton = _empty_brief_skeleton(brief_id)
    return _stamp_system(skeleton, mode="live", status="generating", data_quality="unavailable")


@router.post("/admin/brief/regenerate")
async def regenerate() -> dict[str, str]:
    """Force-regenerate today's brief. Drops the cache and respawns."""
    brief_id = _today_hkt()
    _spawn_generation(brief_id)
    return {"status": "queued", "brief_id": brief_id}
