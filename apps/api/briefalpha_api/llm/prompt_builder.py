"""Strict prompt assembly — never string-concat raw evidence.

Per task 9.6: only fields white-listed in `AliasedEvidence` may flow into
the prompt; any builder that takes a raw evidence dict MUST run it through
`AliasedEvidence(**raw)` first (which strips unknown fields).
"""
from __future__ import annotations

import json
from pathlib import Path

from briefalpha_api.anonymization.replace import AliasedEvidence
from briefalpha_api.llm.schema import LlmRequest, Scope
from briefalpha_api.settings import PROMPTS_DIR

_TEMPLATE_PATHS: dict[str, str] = {
    "stage_a": "stage_a.json",
    "stage_b": "stage_b.json",
    "stage_c": "stage_c.json",
    "qa_local": "qa_local.json",
    "qa_global": "qa_global.json",
}


def load_template(scope: Scope) -> dict:
    fname = _TEMPLATE_PATHS.get(scope)
    if not fname:
        raise ValueError(f"no template for scope={scope}")
    path: Path = PROMPTS_DIR / fname
    return json.loads(path.read_text(encoding="utf-8"))


def build_request(
    *,
    scope: Scope,
    aliased_evidence: list[AliasedEvidence],
    extra_payload: dict | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.2,
) -> LlmRequest:
    template = load_template(scope)
    user_payload = dict(template["user_template"])
    if extra_payload:
        user_payload.update(extra_payload)
    return LlmRequest(
        call_type="text",
        scope=scope,
        template_version=template["template_version"],
        system=template["system"],
        user_payload=user_payload,
        aliased_evidence=aliased_evidence,
        response_schema=template.get("response_schema"),
        max_tokens=max_tokens,
        temperature=temperature,
    )
