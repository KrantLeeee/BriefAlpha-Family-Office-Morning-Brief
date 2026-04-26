"""POST /api/qa — anonymized question-answering against today's evidence pool.

The router is a thin adapter: validation + service invocation + response
shape. The actual safe pipeline lives in `briefalpha_api.qa.service`.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from briefalpha_api.db.session import get_session
from briefalpha_api.qa import run_qa

router = APIRouter()


class QaRequest(BaseModel):
    brief_id: str
    scope: Literal["judgement", "evidence", "global"]
    scope_target_id: str | None = None
    question: str = Field(..., max_length=500)


class QaCitation(BaseModel):
    evidence_id: str
    label: str


class QaResponse(BaseModel):
    answer: str
    cited_evidence_ids: list[str] = []
    citations: list[QaCitation] = []
    insufficient_evidence: bool = False
    validation_passed: bool = True


@router.post("/qa", response_model=QaResponse)
async def qa(req: QaRequest, session=Depends(get_session)) -> QaResponse:
    result = await run_qa(
        session,
        brief_id=req.brief_id,
        scope=req.scope,
        scope_target_id=req.scope_target_id,
        question=req.question,
    )
    return QaResponse(
        answer=result.answer,
        cited_evidence_ids=result.cited_evidence_ids,
        citations=[QaCitation(**c) for c in result.citations],
        insufficient_evidence=result.insufficient_evidence,
        validation_passed=result.validation_passed,
    )
