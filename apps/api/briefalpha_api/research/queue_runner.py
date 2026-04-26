"""Tick-driven worker that drains the research/reanalyze queues.

Single-flight: only one parse runs at a time so it cannot fight the main
brief pipeline for sqlite write locks. Each tick processes at most
`MAX_PER_TICK` jobs to keep latency predictable.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from briefalpha_api.cache import REANALYZE_QUEUE_KEY, RESEARCH_QUEUE_KEY, rpop
from briefalpha_api.db.session import SessionLocal
from briefalpha_api.research.persistence import ChunkInsert, mark_status, persist_chunks_and_evidence
from briefalpha_api.research.storage import decrypted_temp
from briefalpha_api.research.worker import process_research_pdf

log = logging.getLogger("briefalpha.research.queue")

MAX_PER_TICK = 3
HKT = ZoneInfo("Asia/Hong_Kong")

# Process-wide mutex so the per-minute scheduler tick doesn't overlap with
# the previous tick if it's still processing.
_lock = asyncio.Lock()


async def tick() -> int:
    """Drain up to MAX_PER_TICK items from research:queue + reanalyze:queue.

    Returns the number of jobs processed (0 means nothing was queued).
    """
    if _lock.locked():
        log.debug("research worker tick: previous tick still running, skipping")
        return 0
    async with _lock:
        processed = 0
        # Reanalyze first — operator-initiated work is higher priority.
        for _ in range(MAX_PER_TICK):
            payload = await rpop(REANALYZE_QUEUE_KEY)
            if payload is None:
                break
            await _process_one(payload, mode="reanalyze")
            processed += 1
        for _ in range(MAX_PER_TICK - processed):
            payload = await rpop(RESEARCH_QUEUE_KEY)
            if payload is None:
                break
            await _process_one(payload, mode="initial")
            processed += 1
        return processed


async def _process_one(payload: Any, *, mode: str) -> None:
    if not isinstance(payload, dict):
        log.warning("research queue payload not a dict: %r", payload)
        return
    file_id = payload.get("file_id")
    user_id = payload.get("user_id")
    if not file_id or not user_id:
        log.warning("research queue payload missing file_id/user_id: %r", payload)
        return

    log.info("research worker (%s) processing %s", mode, file_id)
    async with SessionLocal() as s:
        await mark_status(s, file_id=file_id, status="parsing")

    universe_tickers: set[str] = set()  # Detection runs on detected_tickers in chunk content; the dict is built lazily.

    parse_result = None
    try:
        with decrypted_temp(user_id, file_id) as pdf_path:
            parse_result = await process_research_pdf(
                file_id=file_id,
                pdf_path=pdf_path,
                universe_tickers=universe_tickers,
                consent_granted=payload.get("consent_state") == "granted",
            )
    except Exception as exc:  # noqa: BLE001
        log.exception("research worker failed for %s: %s", file_id, exc)
        async with SessionLocal() as s:
            await mark_status(
                s,
                file_id=file_id,
                status="failed",
                failures=[{"stage": "worker", "reason": str(exc)[:240]}],
                completed=True,
            )
        return

    chunks = [
        ChunkInsert(
            chunk_id=c.chunk_id,
            page=c.page,
            bbox=c.bbox,
            chunk_type=c.chunk_type,
            heading=c.heading,
            content=c.content,
            detected_tickers=c.detected_tickers,
        )
        for c in parse_result.chunks
    ]

    today_hkt = datetime.now(tz=HKT).strftime("%Y-%m-%d")
    async with SessionLocal() as s:
        from briefalpha_api.research.persistence import get_job_for_user

        try:
            job = await get_job_for_user(s, file_id=file_id, user_id=user_id)
        except FileNotFoundError:
            log.warning("research job vanished mid-parse for %s", file_id)
            return
        await persist_chunks_and_evidence(
            s, job=job, brief_id=today_hkt, chunks=chunks
        )

        report = {
            "filename": job.filename,
            "size_label": f"{round(job.size_bytes / (1024 * 1024), 1)} MB",
            "page_count": len(parse_result.stages and parse_result.stages or []),
            "uploaded_at_hkt": datetime.now(tz=HKT).strftime("%H:%M"),
            "parse_seconds": None,
            "stages": parse_result.stages,
            "tickers_in_universe": parse_result.tickers_in_universe,
            "tickers_external": parse_result.tickers_external,
            "low_confidence_chunks": [],
        }
        await mark_status(
            s,
            file_id=file_id,
            status="ok",
            parse_report=report,
            failures=parse_result.failures,
            completed=True,
        )
    log.info("research worker (%s) finished %s — %d chunks", mode, file_id, len(chunks))
