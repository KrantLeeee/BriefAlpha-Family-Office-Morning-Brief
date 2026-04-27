"""Admin diagnostics + audit_mode toggle.

All endpoints under `/api/admin/*` require the admin token (Bearer).
Diagnostics views aggregate from `audit_log` / `source_health_history`
/ `analytics_event` and the on-disk config so an operator can answer
"why is conservative_brief firing", "which sources are flaky", and
"who toggled audit_mode" without touching SQLite directly.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from briefalpha_api.audit import AuditRecord, record_audit
from briefalpha_api.auth import require_admin_token
from briefalpha_api.cache import get_brief_cache, invalidate_brief_cache
from briefalpha_api.db.models import AuditLog, SourceHealthHistory
from briefalpha_api.db.session import get_session
from briefalpha_api.routers.brief import _generation_state, _spawn_generation, _today_hkt
from briefalpha_api.settings import CONFIG_DIR, get_settings

router = APIRouter()

HKT = ZoneInfo("Asia/Hong_Kong")


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@router.get("/admin/diagnostics/source-health-history")
async def source_health_history(
    hours: int = 24,
    _token: str = Depends(require_admin_token),
    session=Depends(get_session),
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 24 * 7)))
    rows = (
        await session.execute(
            select(SourceHealthHistory)
            .where(SourceHealthHistory.recorded_at >= cutoff)
            .order_by(desc(SourceHealthHistory.recorded_at))
        )
    ).scalars().all()
    return {
        "window_hours": hours,
        "rows": [
            {
                "source_name": r.source_name,
                "status": r.status,
                "detail": r.detail,
                "items_collected": r.items_collected,
                "recorded_at": r.recorded_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/admin/diagnostics/conservative-brief-rate")
async def conservative_brief_rate(
    days: int = 30,
    _token: str = Depends(require_admin_token),
    session=Depends(get_session),
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 90)))
    total_q = (
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.created_at >= cutoff)
        .where(AuditLog.scope.in_(["stage_a", "stage_b", "stage_c"]))
    )
    fail_q = (
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.created_at >= cutoff)
        .where(AuditLog.failure_state.is_not(None))
        .where(AuditLog.scope.in_(["stage_a", "stage_b", "stage_c"]))
    )
    total = (await session.execute(total_q)).scalar_one() or 0
    failed = (await session.execute(fail_q)).scalar_one() or 0
    rate = (failed / total) if total else 0.0
    return {
        "window_days": days,
        "stage_runs": total,
        "failed_runs": failed,
        "conservative_rate": round(rate, 4),
        "alert": rate > 0.10,
    }


@router.get("/admin/diagnostics/audit-mode-history")
async def audit_mode_history(
    _token: str = Depends(require_admin_token),
    session=Depends(get_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(AuditLog)
            .where(AuditLog.scope == "admin_audit_mode_toggle")
            .order_by(desc(AuditLog.created_at))
            .limit(200)
        )
    ).scalars().all()
    return {
        "rows": [
            {
                "request_hash": r.request_hash,
                "audit_mode": r.audit_mode,
                "recorded_at": r.created_at.isoformat(),
                "failure_state": r.failure_state,
            }
            for r in rows
        ]
    }


@router.get("/admin/diagnostics/missing-aliases")
async def missing_aliases(_token: str = Depends(require_admin_token)) -> dict[str, Any]:
    """List universe tickers with no `company_alias_zh.yml` entry."""
    import yaml

    zh_path = CONFIG_DIR / "company_alias_zh.yml"
    overrides_path = CONFIG_DIR / "ticker_sector_overrides.yml"
    zh = yaml.safe_load(zh_path.read_text(encoding="utf-8")) or {} if zh_path.exists() else {}
    overrides = (
        yaml.safe_load(overrides_path.read_text(encoding="utf-8")) or {}
        if overrides_path.exists()
        else {}
    )
    universe_tickers = sorted(set(overrides.keys()))
    missing = [tk for tk in universe_tickers if tk not in zh]
    return {
        "universe_size": len(universe_tickers),
        "with_zh_alias": len(universe_tickers) - len(missing),
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# audit_mode toggle
# ---------------------------------------------------------------------------


class AuditModeToggle(BaseModel):
    mode: Literal["demo", "compliance"]
    confirm_token: str = Field(
        ...,
        min_length=8,
        description="echo of presented admin token; gates accidental flips",
    )
    reason: str = Field(..., min_length=12, max_length=400)


@router.post("/admin/audit-mode")
async def toggle_audit_mode(
    payload: AuditModeToggle,
    token: str = Depends(require_admin_token),
    session=Depends(get_session),
) -> dict[str, Any]:
    if payload.confirm_token != token:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "confirm_token_mismatch",
                    "message": (
                        "confirm_token must equal the presented admin token "
                        "(twin-factor confirmation)."
                    ),
                }
            },
        )
    settings = get_settings()
    previous = settings.audit_mode
    # We don't mutate persistent config here — operators must update
    # `.env` / settings.json. Audit-log entry records intent + reason so
    # the trail is preserved even before the env actually flips.
    rec = AuditRecord(
        request_hash=hashlib.sha256(
            json.dumps(payload.model_dump(), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        response_hash=None,
        scope="admin_audit_mode_toggle",
        cited_evidence_ids=[],
        accuracy_validation_passed=None,
        call_type="admin",
        provider=None,
        model=None,
        template_version=None,
        latency_ms=None,
        failure_state=f"requested_mode:{payload.mode}|reason:{payload.reason[:120]}",
        audit_mode=payload.mode,
    )
    await record_audit(session, rec)
    return {
        "previous_mode": previous,
        "requested_mode": payload.mode,
        "note": (
            "Recorded the toggle intent. Update BRIEFALPHA_AUDIT_MODE "
            "in settings to take effect on next start."
        ),
    }


# ---------------------------------------------------------------------------
# User-facing refresh (Task 2.7)
# ---------------------------------------------------------------------------


@router.post("/admin/data/refresh")
async def refresh_data(request: Request) -> dict[str, Any]:
    """Mode-aware refresh for the frontend Refresh button.

    Demo mode invalidates cache only — the fixture is re-served with a
    fresh `last_refreshed_at` stamp; we do NOT trigger ingestion since
    there is no real data to fetch. Live mode invalidates cache AND
    respawns brief generation, which internally re-runs ingestion.

    Differs from `/admin/brief/regenerate` which unconditionally respawns
    generation; this endpoint is the user-facing surface the UI calls
    and returns mode-aware metadata (refreshed_at_hkt, note) for display.
    """
    mode = getattr(request.app.state, "mode", "live")
    brief_id = _today_hkt()

    await invalidate_brief_cache(brief_id)

    if mode == "demo":
        now = datetime.now(tz=HKT)
        return {
            "status": "demo_refreshed",
            "brief_id": brief_id,
            "refreshed_at_hkt": now.strftime("%H:%M"),
            "note": "示例数据，非实时采集",
        }

    _spawn_generation(brief_id, force=True)
    state = _generation_state.get(brief_id, {})
    return {
        "status": "queued",
        "brief_id": brief_id,
        "generation_status": state.get("status", "generating"),
        "started_at": state.get("started_at"),
    }


@router.get("/admin/data/refresh/status")
async def refresh_status() -> dict[str, Any]:
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
