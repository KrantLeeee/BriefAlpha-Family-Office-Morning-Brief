from __future__ import annotations

import json
import os

import yaml

from briefalpha_api.settings import CONFIG_DIR, SECRETS_DIR, get_settings

_DATA_SOURCES_PATH = CONFIG_DIR / "data_sources.yml"
# The default placeholder UA is "BriefAlpha demo <ops@example.com>".
# Any UA still containing example.com is rejected — SEC fair-use policy
# requires a real contact email so a maintainer can be reached.
_SEC_UA_PLACEHOLDER_MARKER = "example.com"


def check_live_preconditions() -> list[str]:
    issues: list[str] = []
    settings = get_settings()
    provider = settings.llm_provider

    if not _has_llm_key_for(provider):
        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        issues.append(
            f"BRIEFALPHA_LLM_PROVIDER={provider} but no usable LLM provider key. "
            f"Set {env_var} env var, or put a non-placeholder value in "
            f"{SECRETS_DIR / 'llm_api_keys.json'} under '{provider}'."
        )

    sec_issue = _check_sec_user_agent()
    if sec_issue:
        issues.append(sec_issue)

    return issues


def _has_llm_key_for(provider: str) -> bool:
    env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    if (os.getenv(env_var) or "").strip():
        return True
    return _has_secrets_file_key_for(provider)


def _has_secrets_file_key_for(provider: str) -> bool:
    path = SECRETS_DIR / "llm_api_keys.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    value = data.get(provider)
    return (
        isinstance(value, str)
        and bool(value.strip())
        and "replace-me" not in value
    )


def _check_sec_user_agent() -> str | None:
    """Read the SEC user agent the official adapter actually uses.

    The adapter (apps/api/briefalpha_api/ingestion/official.py) reads the
    UA from packages/config/data_sources.yml `sec.user_agent` — NOT from
    any env var. Validating the env var would fail open. The default
    placeholder contains 'example.com' and is rejected.
    """
    if not _DATA_SOURCES_PATH.exists():
        return f"Missing config file: {_DATA_SOURCES_PATH}"
    try:
        cfg = yaml.safe_load(_DATA_SOURCES_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return f"Cannot parse {_DATA_SOURCES_PATH}: {exc}"
    ua = (cfg.get("sec", {}) or {}).get("user_agent", "")
    ua = (ua or "").strip()
    if not ua:
        return (
            f"sec.user_agent is empty in {_DATA_SOURCES_PATH}. "
            "Set it to 'YourApp/version your.email@yourdomain.com' — "
            "SEC RSS rejects requests without it."
        )
    if _SEC_UA_PLACEHOLDER_MARKER in ua.lower():
        return (
            f"sec.user_agent in {_DATA_SOURCES_PATH} is the default placeholder "
            f"({ua!r}). Replace 'example.com' with a real contact email."
        )
    return None
