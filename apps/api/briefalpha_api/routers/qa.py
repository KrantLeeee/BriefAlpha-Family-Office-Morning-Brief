"""POST /api/qa — anonymized question-answering against today's evidence pool.

The router is a thin adapter: validation + service invocation + response
shape. The actual safe pipeline lives in `briefalpha_api.qa.service`.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
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
    failure_reason: str | None = None
    is_demo_response: bool = False


@router.post("/qa", response_model=QaResponse)
async def qa(req: QaRequest, request: Request, session=Depends(get_session)) -> QaResponse:
    mode = getattr(request.app.state, "mode", "live")
    result = await run_qa(
        session,
        brief_id=req.brief_id,
        scope=req.scope,
        scope_target_id=req.scope_target_id,
        question=req.question,
        mode=mode,
    )
    return QaResponse(
        answer=result.answer,
        cited_evidence_ids=result.cited_evidence_ids,
        citations=[QaCitation(**c) for c in result.citations],
        insufficient_evidence=result.insufficient_evidence,
        validation_passed=result.validation_passed,
        failure_reason=result.failure_reason,
        is_demo_response=(result.failure_reason == "demo_mode_prebaked"),
    )
