"""Live-mode precondition tests.

These tests cover the two High-severity bugs the trust-loop review
flagged in the previous implementation:

1. The LLM-key check used to pass if *any* provider key was set, even
   when `BRIEFALPHA_LLM_PROVIDER` pointed at a different provider — so
   live mode could boot with no usable key. We now check the
   provider-specific key.
2. The SEC UA check used to read the env var `SEC_EDGAR_USER_AGENT`,
   but the adapter reads `packages/config/data_sources.yml` `sec.user_agent`.
   We now validate the actual config source the adapter uses, and reject
   the default placeholder (which contains `example.com`).
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import briefalpha_api.config.live_preconditions as lp_mod
from briefalpha_api.config.live_preconditions import check_live_preconditions

_GOOD_UA_YAML = "sec:\n  user_agent: 'BriefAlpha/dev test@mycompany.com'\n"
_PLACEHOLDER_UA_YAML = "sec:\n  user_agent: 'BriefAlpha demo <ops@example.com>'\n"
_EMPTY_UA_YAML = "sec:\n  user_agent: ''\n"


@pytest.fixture
def isolate_env(monkeypatch):
    """Strip relevant env vars and isolate SECRETS_DIR / data_sources path."""
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SEC_EDGAR_USER_AGENT"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def stub_settings(monkeypatch):
    """Return a callable that swaps `get_settings` to return a stub with the
    given llm_provider, regardless of pydantic env-loading."""

    def _set(provider: str) -> None:
        monkeypatch.setattr(
            lp_mod, "get_settings", lambda: SimpleNamespace(llm_provider=provider)
        )

    return _set


@pytest.fixture
def with_yaml(monkeypatch, tmp_path: Path):
    """Point the precondition module at a tmp data_sources.yml."""

    def _write(content: str) -> Path:
        target = tmp_path / "data_sources.yml"
        target.write_text(content, encoding="utf-8")
        monkeypatch.setattr(lp_mod, "_DATA_SOURCES_PATH", target)
        return target

    return _write


@pytest.fixture
def with_secrets(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(lp_mod, "SECRETS_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Provider-specific key check
# ---------------------------------------------------------------------------


def test_passes_with_anthropic_provider_and_anthropic_env_key(
    isolate_env, stub_settings, with_yaml, with_secrets, monkeypatch
):
    stub_settings("anthropic")
    with_yaml(_GOOD_UA_YAML)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert check_live_preconditions() == []


def test_passes_with_openai_provider_and_openai_env_key(
    isolate_env, stub_settings, with_yaml, with_secrets, monkeypatch
):
    stub_settings("openai")
    with_yaml(_GOOD_UA_YAML)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert check_live_preconditions() == []


def test_fails_when_provider_is_openai_but_only_anthropic_env_set(
    isolate_env, stub_settings, with_yaml, with_secrets, monkeypatch
):
    """The original High-severity bug: live mode passed precondition with
    the wrong provider's key, then degraded to the stub at runtime."""
    stub_settings("openai")
    with_yaml(_GOOD_UA_YAML)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    issues = check_live_preconditions()
    assert any("OPENAI_API_KEY" in i for i in issues)
    assert any("openai" in i for i in issues)


def test_fails_when_provider_is_anthropic_but_only_openai_env_set(
    isolate_env, stub_settings, with_yaml, with_secrets, monkeypatch
):
    stub_settings("anthropic")
    with_yaml(_GOOD_UA_YAML)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    issues = check_live_preconditions()
    assert any("ANTHROPIC_API_KEY" in i for i in issues)


def test_passes_with_secrets_file_for_provider(
    isolate_env, stub_settings, with_yaml, with_secrets
):
    stub_settings("anthropic")
    with_yaml(_GOOD_UA_YAML)
    (with_secrets / "llm_api_keys.json").write_text(
        json.dumps({"anthropic": "sk-ant-from-file", "openai": "replace-me"})
    )
    assert check_live_preconditions() == []


def test_fails_when_secrets_file_has_only_other_provider(
    isolate_env, stub_settings, with_yaml, with_secrets
):
    stub_settings("openai")
    with_yaml(_GOOD_UA_YAML)
    (with_secrets / "llm_api_keys.json").write_text(
        json.dumps({"anthropic": "sk-ant-from-file", "openai": "replace-me"})
    )
    issues = check_live_preconditions()
    assert any("OPENAI_API_KEY" in i for i in issues)


def test_fails_with_placeholder_secrets_file_for_provider(
    isolate_env, stub_settings, with_yaml, with_secrets
):
    stub_settings("anthropic")
    with_yaml(_GOOD_UA_YAML)
    (with_secrets / "llm_api_keys.json").write_text(
        json.dumps({"anthropic": "sk-ant-replace-me", "openai": "replace-me"})
    )
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_fails_with_blank_env_value_falls_through_to_secrets(
    isolate_env, stub_settings, with_yaml, with_secrets, monkeypatch
):
    stub_settings("anthropic")
    with_yaml(_GOOD_UA_YAML)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_corrupt_secrets_file_fails_silently(
    isolate_env, stub_settings, with_yaml, with_secrets
):
    stub_settings("anthropic")
    with_yaml(_GOOD_UA_YAML)
    (with_secrets / "llm_api_keys.json").write_text("{not valid json")
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


# ---------------------------------------------------------------------------
# SEC user agent check (now reads YAML, not env var)
# ---------------------------------------------------------------------------


def test_fails_when_sec_user_agent_is_default_placeholder(
    isolate_env, stub_settings, with_yaml, with_secrets, monkeypatch
):
    stub_settings("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with_yaml(_PLACEHOLDER_UA_YAML)
    issues = check_live_preconditions()
    assert any("placeholder" in i.lower() for i in issues)
    assert any("example.com" in i for i in issues)


def test_fails_when_sec_user_agent_empty(
    isolate_env, stub_settings, with_yaml, with_secrets, monkeypatch
):
    stub_settings("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with_yaml(_EMPTY_UA_YAML)
    issues = check_live_preconditions()
    assert any("sec.user_agent" in i for i in issues)


def test_passes_with_real_sec_user_agent(
    isolate_env, stub_settings, with_yaml, with_secrets, monkeypatch
):
    stub_settings("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with_yaml(_GOOD_UA_YAML)
    assert check_live_preconditions() == []


def test_fails_when_data_sources_yaml_missing(
    isolate_env, stub_settings, with_secrets, monkeypatch, tmp_path
):
    stub_settings("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(lp_mod, "_DATA_SOURCES_PATH", tmp_path / "missing.yml")
    issues = check_live_preconditions()
    assert any("Missing config file" in i for i in issues)
