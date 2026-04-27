"""Source-health snapshot aggregator.

Reads `source_health_history` for the last `WINDOW_MINUTES` and reduces it
to one row per source: latest status, latest items_collected, last
detail. Active research uploads are computed separately so the resulting
shape matches the frontend `Brief.source_health` contract.

The aggregated snapshot is persisted to redis at `source_health:latest`
with a 30-minute TTL.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from briefalpha_api.cache import SOURCE_HEALTH_KEY, set_json
from briefalpha_api.db.models import Evidence, ResearchJob, SourceHealthHistory
from briefalpha_api.db.session import SessionLocal

log = logging.getLogger("briefalpha.audit.source_health")

WINDOW_MINUTES = 30
SNAPSHOT_TTL_SECONDS = 30 * 60

# Pretty Chinese labels (frontend renders these as-is in the table).
_LABELS = {
    "yfinance": "行情",
    "stooq": "行情",
    "google_news_rss": "新闻",
    "gdelt": "新闻",
    "gdelt+google": "新闻",
    "finnhub": "新闻",
    "newsapi": "新闻",
    "sec_edgar": "官方公告",
    "hkex": "官方公告",
    "research": "研报",
}


def _label_for(source_name: str) -> str:
    return _LABELS.get(source_name, source_name)


async def aggregate_source_health() -> dict[str, Any]:
    """Compute the snapshot, persist to redis, return the snapshot dict."""
    cutoff = datetime.now(UTC) - timedelta(minutes=WINDOW_MINUTES)
    rows: list[dict[str, Any]] = []
    overall_status = "ok"
    async with SessionLocal() as s:
        # Latest row per source within the window.
        latest_q = (
            select(
                SourceHealthHistory.source_name,
                func.max(SourceHealthHistory.recorded_at).label("max_recorded_at"),
            )
            .where(SourceHealthHistory.recorded_at >= cutoff)
            .group_by(SourceHealthHistory.source_name)
        )
        latest = (await s.execute(latest_q)).all()
        latest_map = {sn: ts for sn, ts in latest}

        if latest_map:
            full_q = select(SourceHealthHistory).where(
                SourceHealthHistory.recorded_at >= cutoff
            )
            full_rows = (await s.execute(full_q)).scalars().all()
            by_source: dict[str, SourceHealthHistory] = {}
            for r in full_rows:
                ts = latest_map.get(r.source_name)
                if ts and r.recorded_at == ts:
                    by_source[r.source_name] = r
            for source_name, r in by_source.items():
                if r.status in {"degraded", "failed"} and overall_status == "ok":
                    overall_status = r.status
                rows.append(
                    {
                        "name": _label_for(source_name),
                        "source_name": source_name,
                        "status": r.status,
                        "detail": r.detail
                        or (
                            f"{r.items_collected} 条"
                            if r.items_collected is not None
                            else "—"
                        ),
                        "recorded_at": r.recorded_at.isoformat(),
                        "is_demo": False,
                    }
                )

        # Research uploads are not a third-party source, but the user needs to
        # know whether parsed research is available for the next brief run.
        # Active jobs take precedence in status; completed jobs/chunks remain
        # visible instead of collapsing back to the misleading "no uploads".
        active_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.status.in_(["queued", "parsing", "reanalyze_queued"])
        )
        active_count = (await s.execute(active_q)).scalar_one() or 0
        ready_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.status == "ok"
        )
        ready_count = (await s.execute(ready_q)).scalar_one() or 0
        chunk_q = select(func.count()).select_from(Evidence).where(
            Evidence.source_tier == "research"
        )
        chunk_count = (await s.execute(chunk_q)).scalar_one() or 0
        rows.append(
            {
                "name": "研报",
                "source_name": "research",
                "status": "active" if active_count > 0 else "ok",
                "detail": _research_detail(
                    active_count=active_count,
                    ready_count=ready_count,
                    chunk_count=chunk_count,
                ),
                "recorded_at": datetime.now(UTC).isoformat(),
                "is_demo": False,
            }
        )

    snapshot = {
        "as_of_hkt": datetime.now(UTC).strftime("%H:%M"),
        "overall": overall_status,
        "rows": rows,
        "window_minutes": WINDOW_MINUTES,
        "computed_at": datetime.now(UTC).isoformat(),
    }
    await set_json(SOURCE_HEALTH_KEY, snapshot, ttl_seconds=SNAPSHOT_TTL_SECONDS)
    log.info(
        "source_health snapshot: overall=%s rows=%d", overall_status, len(rows)
    )
    return snapshot


def _research_detail(*, active_count: int, ready_count: int, chunk_count: int) -> str:
    parts: list[str] = []
    if active_count > 0:
        parts.append(f"{active_count} uploads active")
    if ready_count > 0:
        if chunk_count > 0:
            parts.append(f"{ready_count} uploads ready · {chunk_count} chunks")
        else:
            parts.append(f"{ready_count} uploads ready")
    return " · ".join(parts) if parts else "no uploads"
