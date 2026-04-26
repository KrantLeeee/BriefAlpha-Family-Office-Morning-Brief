"""Audit + source_health writers.

`record_audit_async` is the safe entry point used by the LLM wrapper. It
opens its own session (so callers in deeply nested async contexts don't
have to thread one through), commits, and swallows DB failures behind a
warning log — audit MUST NOT block the request path. Failures are still
visible to operators via the warning stream.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from briefalpha_api.db.models import AuditLog, SourceHealthHistory

log = logging.getLogger("briefalpha.audit")


@dataclass
class AuditRecord:
    request_hash: str
    response_hash: str | None
    scope: str
    cited_evidence_ids: list[str] = field(default_factory=list)
    accuracy_validation_passed: bool | None = None
    call_type: str = "text"
    provider: str | None = None
    model: str | None = None
    template_version: str | None = None
    latency_ms: int | None = None
    failure_state: str | None = None
    audit_mode: str = "demo"
    brief_id: str | None = None


async def record_audit(session: AsyncSession, rec: AuditRecord) -> None:
    """Caller-supplied-session variant. Used by tests and by callers that
    already hold a session."""
    row = AuditLog(
        **asdict(rec),
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.commit()


async def record_audit_async(rec: AuditRecord) -> None:
    """Self-contained variant. Opens a fresh session, swallows DB errors
    so the LLM wrapper can call it from arbitrary contexts without dragging
    a session through the call signature."""
    try:
        from briefalpha_api.db.session import SessionLocal

        async with SessionLocal() as s:
            await record_audit(s, rec)
    except Exception as exc:  # noqa: BLE001
        log.warning("audit write failed (%s): %s", rec.scope, exc)


async def record_source_health(
    session: AsyncSession,
    *,
    source_name: str,
    status: str,
    detail: str | None = None,
    items_collected: int | None = None,
) -> None:
    session.add(
        SourceHealthHistory(
            source_name=source_name,
            status=status,
            detail=detail,
            items_collected=items_collected,
            recorded_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


async def record_source_health_async(
    *,
    source_name: str,
    status: str,
    detail: str | None = None,
    items_collected: int | None = None,
) -> None:
    """Self-contained variant for the ingestion runner."""
    try:
        from briefalpha_api.db.session import SessionLocal

        async with SessionLocal() as s:
            await record_source_health(
                s,
                source_name=source_name,
                status=status,
                detail=detail,
                items_collected=items_collected,
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("source_health write failed (%s): %s", source_name, exc)
