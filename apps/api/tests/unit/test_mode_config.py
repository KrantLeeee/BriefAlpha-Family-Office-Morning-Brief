import pytest

from briefalpha_api.config.mode import resolve_mode


def test_mode_default_is_demo(monkeypatch):
    monkeypatch.delenv("BRIEFALPHA_MODE", raising=False)
    assert resolve_mode() == "demo"


def test_mode_explicit_demo(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "demo")
    assert resolve_mode() == "demo"


def test_mode_explicit_live(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "live")
    assert resolve_mode() == "live"


def test_mode_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "LIVE")
    assert resolve_mode() == "live"


def test_mode_strips_whitespace(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "  demo  ")
    assert resolve_mode() == "demo"


def test_mode_invalid_raises(monkeypatch):
    monkeypatch.setenv("BRIEFALPHA_MODE", "staging")
    with pytest.raises(ValueError) as exc:
        resolve_mode()
    assert "demo" in str(exc.value) or "live" in str(exc.value)
