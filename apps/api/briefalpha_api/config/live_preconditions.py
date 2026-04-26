from __future__ import annotations

import json
import os
from pathlib import Path


def check_live_preconditions() -> list[str]:
    issues: list[str] = []
    if not _has_llm_key():
        issues.append(
            "No LLM provider key configured. "
            "Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
            "or populate data/.secrets/llm_api_keys.json with a non-placeholder value."
        )
    if not (os.getenv("SEC_EDGAR_USER_AGENT") or "").strip():
        issues.append(
            "SEC_EDGAR_USER_AGENT must be set in live mode "
            "(format: 'AppName/version contact@example.com'). SEC RSS requires it."
        )
    return issues


def _has_llm_key() -> bool:
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        if (os.getenv(var) or "").strip():
            return True
    return _has_secrets_file_key()


def _has_secrets_file_key() -> bool:
    path = Path("data/.secrets/llm_api_keys.json")
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    for key in ("anthropic", "openai"):
        value = data.get(key)
        if isinstance(value, str) and value.strip() and value != "replace-me":
            return True
    return False
