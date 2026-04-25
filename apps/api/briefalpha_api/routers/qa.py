"""POST /api/qa.

Stub: until search + LLM wrapper land, returns a deterministic stub answer.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

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
    cited_evidence_ids: list[str]
    citations: list[QaCitation]
    insufficient_evidence: bool = False
    validation_passed: bool = True


@router.post("/qa", response_model=QaResponse)
async def qa(req: QaRequest) -> QaResponse:
    # Pipeline / wrapper not yet implemented — return a placeholder so the
    # frontend QA flow can be exercised end-to-end without LLM.
    return QaResponse(
        answer=(
            "（demo 占位）该回答将在 LLM wrapper + accuracy_validator 启用后由 "
            "evidence-search 提供，引用 evidence_id 出现在抽屉证据卡上。"
        ),
        cited_evidence_ids=["ev_nvda_8k", "ev_reuters_bbg"],
        citations=[
            QaCitation(evidence_id="ev_nvda_8k", label="① SEC EDGAR · 04-24 20:15 EDT"),
            QaCitation(evidence_id="ev_reuters_bbg", label="② 路透 vs 彭博 · ⚠ 冲突"),
        ],
        validation_passed=True,
    )
