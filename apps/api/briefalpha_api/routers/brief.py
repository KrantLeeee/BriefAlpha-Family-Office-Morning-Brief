"""GET /api/brief/today.

Read path (mode-aware):
  HIT, demo  → stamp system={mode:demo, status:ready, data_quality:fixture}
  HIT, live  → stamp system={mode:live, status:ready, data_quality:live}
  MISS, demo → serve fixture + stamp ready fixture metadata; spawn generation
  MISS, live → return empty skeleton + stamp generating metadata; spawn generation

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
from sqlalchemy import select

from briefalpha_api.cache import get_brief_cache, set_brief_cache
from briefalpha_api.db.models import ReviewOverride
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.fixtures.brief import get_demo_brief
from briefalpha_api.pipeline.run import run_full_brief
from briefalpha_api.portfolio.display_names import display_tree

router = APIRouter()
log = logging.getLogger("briefalpha.routers.brief")

HKT = ZoneInfo("Asia/Hong_Kong")


def _today_hkt() -> str:
    return datetime.now(tz=HKT).strftime("%Y-%m-%d")


# Single-flight: once a brief is generating, additional GETs don't queue
# more workers. Use `asyncio.Lock` per brief_id; cleaned up after run.
_inflight: dict[str, asyncio.Task] = {}
_generation_state: dict[str, dict[str, Any]] = {}


def _spawn_generation(brief_id: str, *, force: bool = False) -> None:
    if brief_id in _inflight and not _inflight[brief_id].done():
        return
    if not force and _generation_state.get(brief_id, {}).get("status") == "error":
        return

    _generation_state[brief_id] = {
        "status": "generating",
        "started_at": _now_iso_hkt(),
        "error": None,
    }

    async def _run() -> None:
        try:
            log.info("background brief generation started for %s", brief_id)
            artifact = await run_full_brief(brief_id)
            await set_brief_cache(brief_id, artifact)
            _generation_state[brief_id] = {
                "status": "ready",
                "started_at": _generation_state.get(brief_id, {}).get("started_at"),
                "finished_at": _now_iso_hkt(),
                "error": None,
            }
            log.info("background brief generation complete for %s", brief_id)
        except Exception as exc:  # noqa: BLE001
            _generation_state[brief_id] = {
                "status": "error",
                "started_at": _generation_state.get(brief_id, {}).get("started_at"),
                "finished_at": _now_iso_hkt(),
                "error": str(exc),
            }
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


def _public_brief(brief: dict[str, Any]) -> dict[str, Any]:
    return display_tree(brief)


async def _merge_review_overrides(brief: dict[str, Any], brief_id: str) -> dict[str, Any]:
    """Apply persisted user review actions on top of the brief response.

    Each ReviewOverride row WINS over whatever was set in the brief's
    judgement.review (whether from the live pipeline or fixture). The
    user's explicit action is the single source of truth for status.
    """
    judgements = brief.get("judgements") or []
    if not judgements:
        return brief
    try:
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(ReviewOverride).where(ReviewOverride.brief_id == brief_id)
                )
            ).scalars().all()
            overrides = {r.judgement_id: r for r in rows}
    except Exception as exc:  # noqa: BLE001
        log.warning("review override lookup failed for %s: %s", brief_id, exc)
        return brief
    if not overrides:
        return brief
    for j in judgements:
        ov = overrides.get(j.get("id"))
        if ov is None:
            continue
        existing_review = j.get("review") or {}
        # If there was no review reason on the judgement (i.e. requires_review=False
        # but the user manually marked it), default reason to "data_gap".
        reason = existing_review.get("reason", "data_gap")
        note = ov.note or existing_review.get("note", "")
        merged: dict[str, Any] = {
            "reason": reason,
            "note": note,
            "status": ov.status,
            "reviewed_at": ov.reviewed_at.isoformat() if ov.reviewed_at else None,
        }
        # Preserve any extra metadata the artifact builder attached (e.g.,
        # `kind: "fallback"` so the UI can change copy for system-generated
        # placeholders vs. real AI judgements). The override only owns
        # status / note / reviewed_at; the kind tag is intrinsic to how the
        # judgement was produced and must survive the user's review action.
        if "kind" in existing_review:
            merged["kind"] = existing_review["kind"]
        j["review"] = merged
    return brief


def _empty_brief_skeleton(brief_id: str) -> dict[str, Any]:
    """Minimal Brief shape returned in live mode while generation is in flight.

    All arrays are empty and string fields are blanks; the frontend should
    rely on `system.status == 'generating'` to show a loading state rather
    than render zeros as real data.
    """
    # Local import avoids circulars at module load.
    from briefalpha_api.settings import get_settings

    settings = get_settings()
    return {
        "brief_id": brief_id,
        "brief_date_hkt": brief_id,
        "delivered_at_hkt": "",
        "freeze_window_hkt": "",
        "stale": False,
        "audit_mode": settings.audit_mode,
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
    # Default to "live" if state.mode is unset (lifespan didn't run / atypical
    # TestClient usage) — never accidentally serve fixture in unknown contexts.
    mode = getattr(request.app.state, "mode", "live")
    cached = await get_brief_cache(brief_id)

    if cached is not None:
        cached = await _merge_review_overrides(cached, brief_id)
        data_quality = "live" if mode == "live" else "fixture"
        return _public_brief(
            _stamp_system(cached, mode=mode, status="ready", data_quality=data_quality)
        )

    if mode == "demo":
        _spawn_generation(brief_id)
        fixture = get_demo_brief()
        fixture["brief_id"] = brief_id
        fixture["brief_date_hkt"] = brief_id
        fixture = await _merge_review_overrides(fixture, brief_id)
        return _public_brief(
            _stamp_system(fixture, mode="demo", status="ready", data_quality="fixture")
        )

    # live + cache miss: kick off generation, return skeleton (NEVER fixture).
    # If the latest background run already failed, surface that state instead
    # of silently queuing a retry on every poll.
    _spawn_generation(brief_id)
    skeleton = _empty_brief_skeleton(brief_id)
    # No judgements in skeleton — merge is a no-op, but call for symmetry/future-safety.
    skeleton = await _merge_review_overrides(skeleton, brief_id)
    state = _generation_state.get(brief_id, {})
    status = "error" if state.get("status") == "error" else "generating"
    return _public_brief(
        _stamp_system(skeleton, mode="live", status=status, data_quality="unavailable")
    )


@router.get("/brief/today/status")
async def brief_today_status() -> dict[str, Any]:
    brief_id = _today_hkt()
    cached = await get_brief_cache(brief_id)
    state = _generation_state.get(brief_id, {})
    status = state.get("status")
    if cached is not None and status != "generating":
        status = "ready"
    return {
        "brief_id": brief_id,
        "status": status or ("ready" if cached is not None else "idle"),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "error": state.get("error"),
        "cached": cached is not None,
    }


@router.post("/admin/brief/regenerate")
async def regenerate() -> dict[str, str]:
    """Force-regenerate today's brief. Drops the cache and respawns."""
    brief_id = _today_hkt()
    _spawn_generation(brief_id, force=True)
    return {"status": "queued", "brief_id": brief_id}
