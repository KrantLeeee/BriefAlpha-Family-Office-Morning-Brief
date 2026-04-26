"""Task 5.1: ReviewOverride SQLAlchemy model roundtrip.

Uses the session-scoped tmp sqlite DB provisioned in conftest.py via
Base.metadata.create_all. Confirms the model maps cleanly through
the async engine — covering insert + read.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from briefalpha_api.db.models import ReviewOverride
from briefalpha_api.db.session import SessionLocal


@pytest.mark.asyncio
async def test_review_override_roundtrip():
    async with SessionLocal() as session:
        obj = ReviewOverride(
            brief_id="b-roundtrip",
            judgement_id="j-roundtrip",
            status="reviewed",
            note="n",
        )
        session.add(obj)
        await session.commit()

        fetched = (
            await session.execute(
                select(ReviewOverride).where(
                    ReviewOverride.brief_id == "b-roundtrip",
                    ReviewOverride.judgement_id == "j-roundtrip",
                )
            )
        ).scalar_one()
        assert fetched.brief_id == "b-roundtrip"
        assert fetched.judgement_id == "j-roundtrip"
        assert fetched.status == "reviewed"
        assert fetched.note == "n"
