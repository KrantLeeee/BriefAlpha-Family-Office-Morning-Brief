"""User review actions on judgements.

Records "我已审阅" so the chip state survives page refresh and is
visible across sessions. No auth — single-user MVP. Multi-user
hardening is a follow-up.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from briefalpha_api.db.models import ReviewOverride
from briefalpha_api.db.session import get_session

router = APIRouter()
HKT = ZoneInfo("Asia/Hong_Kong")


class ReviewRequest(BaseModel):
    brief_id: str = Field(..., max_length=64)
    status: Literal["open", "reviewed"]
    note: str = Field(default="", max_length=500)


@router.post("/review/{judgement_id}")
async def mark_review(
    judgement_id: str,
    body: ReviewRequest,
    session=Depends(get_session),
) -> dict[str, Any]:
    existing = (
        await session.execute(
            select(ReviewOverride).where(
                ReviewOverride.brief_id == body.brief_id,
                ReviewOverride.judgement_id == judgement_id,
            )
        )
    ).scalar_one_or_none()

    reviewed_at = datetime.now(tz=HKT) if body.status == "reviewed" else None

    if existing is None:
        existing = ReviewOverride(
            brief_id=body.brief_id,
            judgement_id=judgement_id,
            status=body.status,
            note=body.note,
            reviewed_at=reviewed_at,
        )
        session.add(existing)
    else:
        existing.status = body.status
        existing.note = body.note
        if body.status == "reviewed":
            existing.reviewed_at = reviewed_at

    await session.commit()
    return {
        "status": "ok",
        "judgement_id": judgement_id,
        "review_status": existing.status,
        "reviewed_at": existing.reviewed_at.isoformat() if existing.reviewed_at else None,
    }
