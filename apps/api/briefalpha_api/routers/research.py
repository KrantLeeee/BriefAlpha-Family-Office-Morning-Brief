"""POST /api/research/upload + status / parse_report / re-analyze / delete.

Real implementation backed by SQLite + AES-GCM disk storage + redis queue.
Routes here uniformly use `user_id` from a header (`X-User-Id`); MVP does
not have full session auth, so the header is the trust boundary. The
admin diagnostics path uses the full admin token instead.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from briefalpha_api.cache import REANALYZE_QUEUE_KEY, RESEARCH_QUEUE_KEY, lpush
from briefalpha_api.db.session import get_session
from briefalpha_api.research import (
    ActiveUploadLimitError,
    CrossUserAccessError,
    create_research_job,
    delete_encrypted,
    delete_job_for_user,
    get_job_for_user,
    mark_status,
    write_encrypted,
)
from briefalpha_api.settings import get_settings

router = APIRouter()
log = logging.getLogger("briefalpha.routers.research")

MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB

# Default user_id when the header is absent — single-tenant MVP UX.
DEFAULT_USER_ID = "demo"


def _user_id_dep(x_user_id: str | None = Header(default=None)) -> str:
    return x_user_id or DEFAULT_USER_ID


def _err(code: str, message: str, *, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


@router.post("/research/upload")
async def upload(
    file: UploadFile = File(...),
    consent_state: Literal["granted", "not_granted"] = Form("not_granted"),
    policy_version: str = Form("2026-04-25"),
    user_id: str = Depends(_user_id_dep),
    session=Depends(get_session),
) -> dict[str, Any]:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise _err("unsupported_media_type", "Only PDF uploads are accepted.", status_code=415)

    payload = await file.read()
    if not payload:
        raise _err("empty_file", "Uploaded file is empty.", status_code=400)
    if len(payload) > MAX_PDF_BYTES:
        raise _err("file_too_large", f"PDF exceeds {MAX_PDF_BYTES} bytes.", status_code=413)

    file_id = secrets.token_hex(8)
    settings = get_settings()
    try:
        job = await create_research_job(
            session,
            file_id=file_id,
            user_id=user_id,
            filename=file.filename or f"{file_id}.pdf",
            size_bytes=len(payload),
            consent_state=consent_state,
            policy_version=policy_version,
            active_limit=settings.research_upload_limit,
        )
    except ActiveUploadLimitError as exc:
        raise _err(
            "active_upload_limit",
            str(exc),
            status_code=429,
        )

    write_encrypted(user_id, file_id, payload)
    await lpush(
        RESEARCH_QUEUE_KEY,
        {"file_id": file_id, "user_id": user_id, "consent_state": consent_state},
    )
    log.info("research/upload accepted file_id=%s user=%s bytes=%d", file_id, user_id, len(payload))
    return {"file_id": job.file_id, "status": "queued"}


@router.get("/research/{file_id}")
async def status(
    file_id: str,
    user_id: str = Depends(_user_id_dep),
    session=Depends(get_session),
) -> dict[str, Any]:
    try:
        job = await get_job_for_user(session, file_id=file_id, user_id=user_id)
    except FileNotFoundError:
        raise _err("research_not_found", file_id, status_code=404)
    except CrossUserAccessError:
        raise _err("forbidden", f"file_id '{file_id}' belongs to another user.", status_code=403)
    return {
        "file_id": file_id,
        "status": job.status,
        "consent_state": job.consent_state,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/research/{file_id}/parse_report")
async def parse_report(
    file_id: str,
    user_id: str = Depends(_user_id_dep),
    session=Depends(get_session),
) -> dict[str, Any]:
    try:
        job = await get_job_for_user(session, file_id=file_id, user_id=user_id)
    except FileNotFoundError:
        raise _err("research_not_found", file_id, status_code=404)
    except CrossUserAccessError:
        raise _err("forbidden", f"file_id '{file_id}' belongs to another user.", status_code=403)
    return job.parse_report or {"status": job.status}


@router.post("/research/{file_id}/reanalyze")
async def reanalyze(
    file_id: str,
    user_id: str = Depends(_user_id_dep),
    session=Depends(get_session),
) -> dict[str, Any]:
    try:
        job = await get_job_for_user(session, file_id=file_id, user_id=user_id)
    except FileNotFoundError:
        raise _err("research_not_found", file_id, status_code=404)
    except CrossUserAccessError:
        raise _err("forbidden", f"file_id '{file_id}' belongs to another user.", status_code=403)

    await mark_status(session, file_id=file_id, status="reanalyze_queued")
    await lpush(
        REANALYZE_QUEUE_KEY,
        {"file_id": file_id, "user_id": user_id, "consent_state": job.consent_state},
    )
    return {"file_id": file_id, "status": "reanalyze_queued"}


@router.delete("/research/{file_id}")
async def delete(
    file_id: str,
    user_id: str = Depends(_user_id_dep),
    session=Depends(get_session),
) -> dict[str, Any]:
    try:
        await delete_job_for_user(session, file_id=file_id, user_id=user_id)
    except FileNotFoundError:
        # Idempotent — return success even if it was already gone.
        return {"file_id": file_id, "status": "deleted"}
    except CrossUserAccessError:
        raise _err("forbidden", f"file_id '{file_id}' belongs to another user.", status_code=403)
    delete_encrypted(user_id, file_id)
    return {"file_id": file_id, "status": "deleted"}
