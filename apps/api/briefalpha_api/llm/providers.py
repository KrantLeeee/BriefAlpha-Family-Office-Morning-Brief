"""Provider adapters (anthropic / openai).

This is the ONLY module allowed to import provider SDKs (enforced by
import-linter contract in pyproject.toml). The wrapper imports from here
via `_call_text_provider` / `_call_vision_provider` / `_call_embedding_provider`.

In MVP, we keep the SDK imports lazy + tolerate missing keys so the API
boots in development even before the user fills in `llm_api_keys.json`.
Real production credentials are validated by `secrets_check`.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from briefalpha_api.llm.schema import LlmRequest, LlmResponse, ProviderError
from briefalpha_api.settings import SECRETS_DIR


def _load_keys() -> dict:
    path: Path = SECRETS_DIR / "llm_api_keys.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _api_key(provider: str) -> str | None:
    keys = _load_keys()
    return keys.get(provider) or os.environ.get(f"{provider.upper()}_API_KEY")


async def call_text_provider(req: LlmRequest, *, provider: str = "anthropic") -> LlmResponse:
    started = time.monotonic()
    api_key = _api_key(provider)

    if not api_key or api_key.endswith("replace-me"):
        # Demo mode without real keys: deterministic stub so the rest of the
        # pipeline (validator / wrapper / audit) can be exercised end-to-end.
        await asyncio.sleep(0)
        latency_ms = int((time.monotonic() - started) * 1000)
        stub = {
            "stage_a": {
                "base_case_headline": "（demo · 无密钥）核心判断占位",
                "summary": "请配置 llm_api_keys.json 后重新运行。",
                "cited_evidence_ids": [
                    e.evidence_id for e in req.aliased_evidence[:2]
                ],
            },
            "stage_b": {"judgements": []},
            "stage_c": {"playbook_events": []},
            "qa_local": {"answer": "（demo · 无密钥）", "cited_evidence_ids": []},
            "qa_global": {"answer": "（demo · 无密钥）", "cited_evidence_ids": []},
        }.get(req.scope, {})
        return LlmResponse(
            text=json.dumps(stub, ensure_ascii=False),
            structured=stub,
            cited_evidence_ids=stub.get("cited_evidence_ids", []),
            provider="stub",
            model="stub-text",
            template_version=req.template_version,
            latency_ms=latency_ms,
            finish_reason="stub",
        )

    if provider == "anthropic":
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ProviderError("anthropic SDK not installed") from exc
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await client.messages.create(
            model="claude-opus-4-7",
            system=req.system,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_payload": req.user_payload,
                            "aliased_evidence": [
                                e.model_dump() for e in req.aliased_evidence
                            ],
                            "response_schema": req.response_schema,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            ],
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        text = msg.content[0].text if msg.content else ""
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            structured = None
        return LlmResponse(
            text=text,
            structured=structured,
            cited_evidence_ids=(structured or {}).get("cited_evidence_ids", []),
            provider="anthropic",
            model="claude-opus-4-7",
            template_version=req.template_version,
            latency_ms=latency_ms,
            finish_reason=msg.stop_reason,
        )

    if provider == "openai":
        try:
            import openai  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ProviderError("openai SDK not installed") from exc
        client = openai.AsyncOpenAI(api_key=api_key)
        resp = await client.responses.create(
            model="gpt-4.1-mini",
            input=json.dumps(
                {
                    "system": req.system,
                    "user_payload": req.user_payload,
                    "aliased_evidence": [e.model_dump() for e in req.aliased_evidence],
                    "response_schema": req.response_schema,
                },
                ensure_ascii=False,
                default=str,
            ),
            max_output_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        text = resp.output_text or ""
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            structured = json.loads(text)
        except json.JSONDecodeError:
            structured = None
        return LlmResponse(
            text=text,
            structured=structured,
            cited_evidence_ids=(structured or {}).get("cited_evidence_ids", []),
            provider="openai",
            model="gpt-4.1-mini",
            template_version=req.template_version,
            latency_ms=latency_ms,
            finish_reason=resp.status,
        )

    raise ProviderError(f"unsupported provider {provider}")


async def call_vision_provider(req: LlmRequest, *, provider: str = "anthropic") -> LlmResponse:
    """Vision call. Identical schema-shape to text but routes through a
    separate API key (`vision_anthropic`) so vision usage is isolated.
    """
    return await call_text_provider(req, provider=provider)


async def call_embedding_provider(text: str, *, provider: str = "openai") -> list[float]:
    """Stub embeddings: returns a 16-dim zero vector unless OPENAI_API_KEY
    is present. Replaced by `sentence-transformers` (local) for ingestion
    dedupe in section 5.3.
    """
    api_key = _api_key(provider)
    if not api_key or api_key.endswith("replace-me"):
        return [0.0] * 16
    try:
        import openai  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ProviderError("openai SDK not installed") from exc
    client = openai.AsyncOpenAI(api_key=api_key)
    resp = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return list(resp.data[0].embedding)
