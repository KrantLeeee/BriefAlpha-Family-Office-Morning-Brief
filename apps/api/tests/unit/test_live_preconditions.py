import json
from pathlib import Path

import pytest

from briefalpha_api.config.live_preconditions import check_live_preconditions


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SEC_EDGAR_USER_AGENT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_passes_with_anthropic_key_and_sec_user_agent(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    assert check_live_preconditions() == []


def test_passes_with_openai_key_and_sec_user_agent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    assert check_live_preconditions() == []


def test_fails_without_any_llm_key(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_fails_without_sec_user_agent(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    issues = check_live_preconditions()
    assert any("SEC_EDGAR_USER_AGENT" in i for i in issues)


def test_fails_with_blank_llm_env_value(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_passes_with_secrets_file(_isolate_env: Path, monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    secrets_dir = _isolate_env / "data" / ".secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "llm_api_keys.json").write_text(
        json.dumps({"anthropic": "sk-ant-from-file", "openai": "replace-me"})
    )
    assert check_live_preconditions() == []


def test_secrets_file_with_only_placeholder_fails(_isolate_env: Path, monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    secrets_dir = _isolate_env / "data" / ".secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "llm_api_keys.json").write_text(
        json.dumps({"anthropic": "replace-me", "openai": "replace-me"})
    )
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_secrets_file_corrupt_json_fails_silently(_isolate_env: Path, monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    secrets_dir = _isolate_env / "data" / ".secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "llm_api_keys.json").write_text("{not valid json")
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)
