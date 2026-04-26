"""Research upload persistence: limits, cross-user, delete cascades."""
from __future__ import annotations

import pytest
from sqlalchemy import delete

from briefalpha_api.db.models import ConsentLog, Evidence, ResearchChunk, ResearchJob
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.research import (
    ActiveUploadLimitError,
    ChunkInsert,
    CrossUserAccessError,
    create_research_job,
    delete_job_for_user,
    get_job_for_user,
    persist_chunks_and_evidence,
)


async def _purge() -> None:
    async with SessionLocal() as s:
        await s.execute(delete(ResearchChunk))
        await s.execute(delete(ResearchJob))
        await s.execute(delete(ConsentLog))
        await s.execute(delete(Evidence))
        await s.commit()


@pytest.mark.asyncio
async def test_active_upload_limit_enforced() -> None:
    await _purge()
    async with SessionLocal() as s:
        for i in range(5):
            await create_research_job(
                s,
                file_id=f"f{i}",
                user_id="u1",
                filename=f"f{i}.pdf",
                size_bytes=1000,
                consent_state="not_granted",
                policy_version="2026-04-25",
                active_limit=5,
            )
        with pytest.raises(ActiveUploadLimitError):
            await create_research_job(
                s,
                file_id="f5",
                user_id="u1",
                filename="f5.pdf",
                size_bytes=1000,
                consent_state="not_granted",
                policy_version="2026-04-25",
                active_limit=5,
            )
    await _purge()


@pytest.mark.asyncio
async def test_cross_user_access_forbidden() -> None:
    await _purge()
    async with SessionLocal() as s:
        await create_research_job(
            s,
            file_id="ff",
            user_id="alice",
            filename="ff.pdf",
            size_bytes=1000,
            consent_state="granted",
            policy_version="2026-04-25",
            active_limit=5,
        )
        with pytest.raises(CrossUserAccessError):
            await get_job_for_user(s, file_id="ff", user_id="bob")
    await _purge()


@pytest.mark.asyncio
async def test_delete_cascades_to_evidence_and_chunks() -> None:
    await _purge()
    async with SessionLocal() as s:
        job = await create_research_job(
            s,
            file_id="del1",
            user_id="alice",
            filename="del1.pdf",
            size_bytes=2048,
            consent_state="granted",
            policy_version="2026-04-25",
            active_limit=5,
        )
        await persist_chunks_and_evidence(
            s,
            job=job,
            brief_id="2026-04-25",
            chunks=[
                ChunkInsert(
                    chunk_id="c_del_1",
                    page=1,
                    bbox=None,
                    chunk_type="text",
                    heading="标题",
                    content="测试段落 NVDA",
                    detected_tickers=["NVDA"],
                )
            ],
        )

    async with SessionLocal() as s:
        await delete_job_for_user(s, file_id="del1", user_id="alice")

    async with SessionLocal() as s:
        from sqlalchemy import select

        chunks = (await s.execute(select(ResearchChunk))).scalars().all()
        evs = (
            await s.execute(select(Evidence).where(Evidence.brief_id == "2026-04-25"))
        ).scalars().all()
        assert chunks == [], "chunks not cascaded"
        # Evidence row generated for the chunk should have been removed too.
        assert all(e.source_tier != "research" for e in evs), "research evidence rows leaked"
    await _purge()


@pytest.mark.asyncio
async def test_consent_log_persisted() -> None:
    await _purge()
    async with SessionLocal() as s:
        await create_research_job(
            s,
            file_id="ff2",
            user_id="alice",
            filename="ff2.pdf",
            size_bytes=1000,
            consent_state="granted",
            policy_version="2026-04-25",
            active_limit=5,
        )
        from sqlalchemy import select

        rows = (await s.execute(select(ConsentLog))).scalars().all()
        assert len(rows) == 1
        assert rows[0].file_id == "ff2"
        assert rows[0].consent_state == "granted"
    await _purge()
