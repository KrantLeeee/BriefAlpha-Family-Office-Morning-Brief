"""Defensive backwards-compat tests for the symbol-map loader.

Even with the refresh job now writing the correct shape, users may
still have stale on-disk files from the old buggy refresh path. The
loader should handle both shapes for SEC, and emit a clear warning
(not silently empty) for HKEX.
"""
from __future__ import annotations

import json
from pathlib import Path

import briefalpha_api.ingestion.symbol_map as sm


def test_loader_handles_raw_sec_json_inline(monkeypatch, tmp_path: Path):
    """Backwards-compat: even if the on-disk file is the raw SEC JSON
    shape (pre-transform), _sec_mappings should still produce a
    non-empty ticker→CIK map."""
    sec_file = tmp_path / "sec.json"
    sec_file.write_text(
        json.dumps({"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA"}})
    )
    monkeypatch.setattr(sm, "_SEC_FILE", sec_file)
    sm._sec_mappings.cache_clear()

    assert sm.cik_for("NVDA") == "0001045810"


def test_loader_handles_transformed_sec_json(monkeypatch, tmp_path: Path):
    sec_file = tmp_path / "sec.json"
    sec_file.write_text(json.dumps({"mappings": {"NVDA": "0001045810"}}))
    monkeypatch.setattr(sm, "_SEC_FILE", sec_file)
    sm._sec_mappings.cache_clear()

    assert sm.cik_for("NVDA") == "0001045810"


def test_loader_returns_none_for_unknown_sec_ticker(monkeypatch, tmp_path: Path):
    sec_file = tmp_path / "sec.json"
    sec_file.write_text(json.dumps({"mappings": {"NVDA": "0001045810"}}))
    monkeypatch.setattr(sm, "_SEC_FILE", sec_file)
    sm._sec_mappings.cache_clear()

    assert sm.cik_for("UNKNOWN") is None


def test_loader_handles_transformed_hkex_json(monkeypatch, tmp_path: Path):
    hkex_file = tmp_path / "hkex.json"
    hkex_file.write_text(json.dumps({"mappings": {"700.HK": "00700"}}))
    monkeypatch.setattr(sm, "_HKEX_FILE", hkex_file)
    sm._hkex_mappings.cache_clear()

    assert sm.hkex_code_for("700.HK") == "00700"
