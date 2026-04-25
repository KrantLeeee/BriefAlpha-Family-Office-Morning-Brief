"""POST /api/research/upload + status / parse_report / re-analyze / delete.

Stubbed for the demo: persists in-memory job records so the upload drawer
flow can be exercised. Real implementation lives in section 14.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

router = APIRouter()

# Ephemeral demo store. Replaced by SQLite in section 14.
_JOBS: dict[str, dict[str, Any]] = {}


def _demo_parse_report(filename: str) -> dict[str, Any]:
    return {
        "filename": filename,
        "size_label": "7.2 MB",
        "page_count": 28,
        "uploaded_at_hkt": "08:18",
        "parse_seconds": 23,
        "stages": [
            {"name": "extraction", "status": "ok", "detail": "27 / 28 pages OK"},
            {"name": "ocr_fallback", "status": "ok", "detail": "1 page recovered"},
            {"name": "vision_caption", "status": "consent_required", "detail": "skipped"},
            {"name": "chunking", "status": "ok", "detail": "186 chunks"},
            {"name": "ticker_detection", "status": "ok", "detail": "12 tickers"},
            {"name": "fts_dedupe", "status": "ok", "detail": "3 duplicates dropped"},
            {"name": "merge_pool", "status": "ok", "detail": "183 chunks merged"},
        ],
        "tickers_in_universe": ["NVDA", "0700.HK", "AAPL"],
        "tickers_external": ["BABA", "BIDU"],
        "low_confidence_chunks": [
            {
                "chunk_id": "c_42",
                "page": 12,
                "reason": "OCR confidence 0.62",
                "preview": "数据中心营收 2026 年或..."
            }
        ],
    }


@router.post("/research/upload")
async def upload(
    file: UploadFile = File(...),
    consent_state: Literal["granted", "not_granted"] = Form("not_granted"),
    policy_version: str = Form("2026-04-25"),
) -> dict[str, Any]:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=415,
            detail={"error": {"code": "unsupported_media_type",
                              "message": "Only PDF uploads are accepted."}},
        )
    file_id = secrets.token_hex(8)
    _JOBS[file_id] = {
        "file_id": file_id,
        "filename": file.filename,
        "consent_state": consent_state,
        "policy_version": policy_version,
        "status": "parsing",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parse_report": _demo_parse_report(file.filename or "research.pdf"),
    }
    return {"file_id": file_id, "status": "queued"}


@router.get("/research/{file_id}")
async def status(file_id: str) -> dict[str, Any]:
    job = _JOBS.get(file_id)
    if not job:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "research_not_found", "message": file_id}
        })
    return {"file_id": file_id, "status": "ok", "consent_state": job["consent_state"]}


@router.get("/research/{file_id}/parse_report")
async def parse_report(file_id: str) -> dict[str, Any]:
    job = _JOBS.get(file_id)
    if not job:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "research_not_found", "message": file_id}
        })
    return job["parse_report"]


@router.post("/research/{file_id}/reanalyze")
async def reanalyze(file_id: str) -> dict[str, Any]:
    job = _JOBS.get(file_id)
    if not job:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "research_not_found", "message": file_id}
        })
    return {"file_id": file_id, "status": "reanalyze_queued"}


@router.delete("/research/{file_id}")
async def delete(file_id: str) -> dict[str, Any]:
    if file_id in _JOBS:
        del _JOBS[file_id]
    return {"file_id": file_id, "status": "deleted"}
