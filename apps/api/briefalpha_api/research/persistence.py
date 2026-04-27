"""DB-backed CRUD for research jobs + chunks.

The router and the worker both use this module so they share invariants:
  - active uploads ≤ 5 per user (PRD §6.2),
  - cross-user access raises a sentinel `CrossUserAccessError`,
  - deleting a job also removes its chunks, evidence rows, and FTS index,
  - chunks are indexed into both `evidence` and `evidence_fts` so QA /
    drawer searches see them.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from briefalpha_api.db.models import (
    ConsentLog,
    Evidence,
    ResearchChunk,
    ResearchJob,
)
from briefalpha_api.search.fts import index_evidence, remove_evidence_index

ACTIVE_STATUSES = ("queued", "parsing", "reanalyze_queued")


class CrossUserAccessError(PermissionError):
    """Raised when a request's user_id doesn't match the job's owner."""


class ActiveUploadLimitError(RuntimeError):
    """Raised when a user tries to upload more than the active-upload cap."""


@dataclass
class ChunkInsert:
    chunk_id: str
    page: int
    bbox: tuple[float, float, float, float] | None
    chunk_type: str
    heading: str | None
    content: str
    detected_tickers: list[str]


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------


async def count_active_for_user(session: AsyncSession, *, user_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(ResearchJob)
        .where(ResearchJob.user_id == user_id)
        .where(ResearchJob.status.in_(ACTIVE_STATUSES))
    )
    return int((await session.execute(stmt)).scalar_one() or 0)


async def create_research_job(
    session: AsyncSession,
    *,
    file_id: str,
    user_id: str,
    filename: str,
    size_bytes: int,
    consent_state: str,
    policy_version: str,
    active_limit: int,
) -> ResearchJob:
    active = await count_active_for_user(session, user_id=user_id)
    if active >= active_limit:
        raise ActiveUploadLimitError(
            f"user '{user_id}' has {active} active uploads (limit {active_limit})"
        )
    job = ResearchJob(
        file_id=file_id,
        user_id=user_id,
        filename=filename,
        size_bytes=size_bytes,
        status="queued",
        parse_report={},
        failures=[],
        consent_state=consent_state,
    )
    session.add(job)
    session.add(
        ConsentLog(
            user_id=user_id,
            file_id=file_id,
            policy_version=policy_version,
            consent_state=consent_state,
            recorded_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()
    await session.refresh(job)
    return job


async def get_job_for_user(
    session: AsyncSession,
    *,
    file_id: str,
    user_id: str,
) -> ResearchJob:
    job = await session.get(ResearchJob, file_id)
    if job is None:
        raise FileNotFoundError(file_id)
    if job.user_id != user_id:
        raise CrossUserAccessError(
            f"user '{user_id}' may not access file_id '{file_id}'"
        )
    return job


async def list_jobs_for_user(
    session: AsyncSession,
    *,
    user_id: str,
    limit: int = 50,
) -> list[ResearchJob]:
    stmt = (
        select(ResearchJob)
        .where(ResearchJob.user_id == user_id)
        .order_by(ResearchJob.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_status(
    session: AsyncSession,
    *,
    file_id: str,
    status: str,
    parse_report: dict[str, Any] | None = None,
    failures: list[dict[str, Any]] | None = None,
    completed: bool = False,
) -> None:
    job = await session.get(ResearchJob, file_id)
    if job is None:
        return
    job.status = status
    if parse_report is not None:
        job.parse_report = parse_report
    if failures is not None:
        job.failures = failures
    if completed:
        job.completed_at = datetime.now(timezone.utc)
    await session.commit()


async def delete_job_for_user(
    session: AsyncSession,
    *,
    file_id: str,
    user_id: str,
) -> None:
    job = await get_job_for_user(session, file_id=file_id, user_id=user_id)

    # Pull out chunk + evidence_id list before we cascade-delete.
    chunks = (
        await session.execute(
            select(ResearchChunk).where(ResearchChunk.file_id == file_id)
        )
    ).scalars().all()
    evidence_ids = [c.evidence_id for c in chunks if c.evidence_id]

    for ev_id in evidence_ids:
        await remove_evidence_index(session, evidence_id=ev_id)
    await session.execute(
        delete(Evidence).where(Evidence.evidence_id.in_(evidence_ids))
    )
    await session.execute(
        delete(ResearchChunk).where(ResearchChunk.file_id == file_id)
    )
    await session.delete(job)
    await session.commit()


# ---------------------------------------------------------------------------
# Chunk + evidence persistence (used by the worker after parse)
# ---------------------------------------------------------------------------


def _evidence_id_for(file_id: str, chunk_id: str) -> str:
    return hashlib.sha1(f"research|{file_id}|{chunk_id}".encode("utf-8")).hexdigest()[
        :16
    ]


async def persist_chunks_and_evidence(
    session: AsyncSession,
    *,
    job: ResearchJob,
    brief_id: str,
    chunks: list[ChunkInsert],
) -> int:
    """Write chunks + a 1:1 evidence row per chunk, and index FTS."""
    written = 0
    now = datetime.now(timezone.utc)
    for ch in chunks:
        evidence_id = _evidence_id_for(job.file_id, ch.chunk_id)
        # Skip chunk if we've already persisted it (idempotent re-analyze).
        existing = await session.get(ResearchChunk, ch.chunk_id)
        if existing is not None:
            continue

        session.add(
            ResearchChunk(
                chunk_id=ch.chunk_id,
                file_id=job.file_id,
                user_id=job.user_id,
                brief_id=brief_id,
                page=ch.page,
                bbox=(
                    {"x0": ch.bbox[0], "y0": ch.bbox[1], "x1": ch.bbox[2], "y1": ch.bbox[3]}
                    if ch.bbox
                    else None
                ),
                chunk_type=ch.chunk_type,
                heading=ch.heading,
                content=ch.content,
                detected_tickers=ch.detected_tickers,
                evidence_id=evidence_id,
            )
        )
        session.add(
            Evidence(
                evidence_id=evidence_id,
                brief_id=brief_id,
                source_tier="research",
                source_reliability=0.5,
                title=ch.heading or f"{job.filename} · p{ch.page}",
                excerpt=ch.content,
                quote_span=None,
                detected_tickers=ch.detected_tickers,
                chunk_type=ch.chunk_type,
                asset_class=None,
                exposure_bucket=None,
                published_at=now,
                fetched_at=now,
                base_score=0.4,
                final_impact_score=0.4,
                score_breakdown={"source_name": "research", "reliability": 0.5},
                selected_for_llm=False,
                conflict=False,
                requires_review=False,
                supplementary_sources=[{"source_name": "research", "url": f"research://{job.file_id}"}],
                raw_source_url=f"research://{job.file_id}#p{ch.page}",
            )
        )
        await index_evidence(
            session,
            evidence_id=evidence_id,
            brief_id=brief_id,
            title=ch.heading or f"{job.filename} · p{ch.page}",
            excerpt=ch.content,
            detected_tickers=ch.detected_tickers,
            chunk_type=ch.chunk_type,
            source_tier="research",
        )
        written += 1
    await session.commit()
    return written
