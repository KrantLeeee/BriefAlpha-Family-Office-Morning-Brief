"""LlmRequest / LlmResponse pydantic models (whitelisted fields)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from briefalpha_api.anonymization.replace import AliasedEvidence

CallType = Literal["text", "vision", "embedding"]
Scope = Literal["stage_a", "stage_b", "stage_c", "qa_local", "qa_global", "vision"]


class LlmRequest(BaseModel):
    """Whitelisted request payload — no fields outside this schema are
    allowed past the wrapper boundary."""

    model_config = ConfigDict(extra="forbid")

    call_type: CallType
    scope: Scope
    template_version: str
    system: str
    user_payload: dict[str, Any]
    aliased_evidence: list[AliasedEvidence] = Field(default_factory=list)
    response_schema: dict[str, Any] | None = None
    max_tokens: int = 1500
    temperature: float = 0.2


class LlmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    structured: dict[str, Any] | None = None
    embedding: list[float] | None = None
    cited_evidence_ids: list[str] = Field(default_factory=list)
    provider: str
    model: str
    template_version: str
    latency_ms: int
    finish_reason: str | None = None


class ProviderError(RuntimeError):
    """Raised when a provider call cannot be completed."""
