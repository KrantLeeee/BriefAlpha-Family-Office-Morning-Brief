"""Startup secret-file validation.

PRD §6.4 requires:
- alias_key (AES-GCM key) at data/.secrets/alias_key
- llm_api_keys.json at data/.secrets/llm_api_keys.json
- admin_token at data/.secrets/admin_token
- All files mode 0600
- SEC EDGAR `user_agent` configured in data_sources.yml
Failing any of these MUST prevent the API from starting.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import yaml

from briefalpha_api.settings import CONFIG_DIR, SECRETS_DIR


class SecretsConfigurationError(RuntimeError):
    """Raised when required secrets / configs are missing or unsafe."""


def _require_file(path: Path, *, hint: str) -> None:
    if not path.exists():
        raise SecretsConfigurationError(
            f"Missing required secret '{path}'. {hint}"
        )
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise SecretsConfigurationError(
            f"Secret '{path}' has overly permissive mode {oct(mode)}. "
            "Run `chmod 600` on it."
        )


def verify_secrets() -> None:
    if os.environ.get("BRIEFALPHA_SKIP_SECRETS_CHECK") == "1":
        # Used in unit tests / CI where secrets are not provisioned.
        return

    _require_file(
        SECRETS_DIR / "alias_key",
        hint="Run `bash scripts/init_secrets.sh` to generate it.",
    )
    _require_file(
        SECRETS_DIR / "admin_token",
        hint="Run `bash scripts/init_secrets.sh` to generate it.",
    )

    keys_path = SECRETS_DIR / "llm_api_keys.json"
    _require_file(
        keys_path,
        hint="Create it with at least an `anthropic` or `openai` API key.",
    )
    try:
        keys = json.loads(keys_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SecretsConfigurationError(
            f"`{keys_path}` is not valid JSON: {exc}"
        ) from exc
    if not any(provider in keys for provider in ("anthropic", "openai")):
        raise SecretsConfigurationError(
            f"`{keys_path}` must contain at least one of: anthropic, openai."
        )

    sources_path = CONFIG_DIR / "data_sources.yml"
    if not sources_path.exists():
        raise SecretsConfigurationError(
            f"Missing config `{sources_path}`."
        )
    sources = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
    sec_cfg = sources.get("sec", {})
    user_agent = sec_cfg.get("user_agent")
    if not user_agent or "@" not in user_agent:
        raise SecretsConfigurationError(
            "`data_sources.yml.sec.user_agent` must be a contact email "
            "string (SEC EDGAR fair-use policy)."
        )
