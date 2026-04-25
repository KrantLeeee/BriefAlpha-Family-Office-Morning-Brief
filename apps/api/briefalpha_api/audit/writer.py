"""Audit + source_health writers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from briefalpha_api.db.models import AuditLog, SourceHealthHistory


@dataclass
class AuditRecord:
    request_hash: str
    response_hash: str | None
    scope: str
    cited_evidence_ids: list[str]
    accuracy_validation_passed: bool | None
    call_type: str
    provider: str | None
    model: str | None
    template_version: str | None
    latency_ms: int | None
    failure_state: str | None
    audit_mode: str
    brief_id: str | None = None


async def record_audit(session: AsyncSession, rec: AuditRecord) -> None:
    row = AuditLog(
        **asdict(rec),
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.commit()


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
