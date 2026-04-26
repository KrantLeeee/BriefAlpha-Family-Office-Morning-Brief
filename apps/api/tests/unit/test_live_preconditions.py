import json

import pytest

import briefalpha_api.config.live_preconditions as lp_mod
from briefalpha_api.config.live_preconditions import check_live_preconditions


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "SEC_EDGAR_USER_AGENT"):
        monkeypatch.delenv(var, raising=False)


def test_passes_with_anthropic_key_and_sec_user_agent(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    assert check_live_preconditions() == []


def test_passes_with_openai_key_and_sec_user_agent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    assert check_live_preconditions() == []


def test_fails_without_any_llm_key(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    monkeypatch.setattr(lp_mod, "SECRETS_DIR", tmp_path)
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_fails_without_sec_user_agent(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    issues = check_live_preconditions()
    assert any("SEC_EDGAR_USER_AGENT" in i for i in issues)


def test_fails_with_blank_llm_env_value(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    monkeypatch.setattr(lp_mod, "SECRETS_DIR", tmp_path)
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_passes_with_secrets_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    monkeypatch.setattr(lp_mod, "SECRETS_DIR", tmp_path)
    (tmp_path / "llm_api_keys.json").write_text(
        json.dumps({"anthropic": "sk-ant-from-file", "openai": "replace-me"})
    )
    assert check_live_preconditions() == []


def test_secrets_file_with_only_placeholder_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    monkeypatch.setattr(lp_mod, "SECRETS_DIR", tmp_path)
    (tmp_path / "llm_api_keys.json").write_text(
        json.dumps({"anthropic": "replace-me", "openai": "replace-me"})
    )
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_secrets_file_corrupt_json_fails_silently(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    monkeypatch.setattr(lp_mod, "SECRETS_DIR", tmp_path)
    (tmp_path / "llm_api_keys.json").write_text("{not valid json")
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)


def test_secrets_file_with_init_script_placeholder_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "BriefAlpha/dev test@example.com")
    monkeypatch.setattr(lp_mod, "SECRETS_DIR", tmp_path)
    (tmp_path / "llm_api_keys.json").write_text(
        json.dumps({"anthropic": "sk-ant-replace-me", "openai": "sk-replace-me"})
    )
    issues = check_live_preconditions()
    assert any("LLM provider key" in i for i in issues)
