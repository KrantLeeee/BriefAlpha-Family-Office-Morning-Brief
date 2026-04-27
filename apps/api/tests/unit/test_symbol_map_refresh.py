"""Tests for the SEC + HKEX symbol-map transform helpers.

Both `_transform_sec` and `_transform_hkex` exist because the upstream
files (raw SEC JSON and an .xlsx workbook) do not match the loader's
expected `{"mappings": {ticker: code}}` shape. These tests pin the
transforms so the refresh job stays in sync with the loader.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from briefalpha_api.scheduler.jobs import _transform_hkex, _transform_sec


def test_sec_transform_extracts_ticker_and_pads_cik():
    raw = json.dumps(
        {
            "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA"},
            "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet"},
        }
    ).encode("utf-8")
    out = _transform_sec(raw)
    payload = json.loads(out.decode("utf-8"))
    assert payload["mappings"]["NVDA"] == "0001045810"
    assert payload["mappings"]["GOOGL"] == "0001652044"


def test_sec_transform_skips_malformed_entries():
    raw = json.dumps(
        {
            "0": {"cik_str": 1, "ticker": "X"},
            "1": "not a dict",
            "2": {"cik_str": 2},  # missing ticker
            "3": {"ticker": "Y"},  # missing cik
        }
    ).encode("utf-8")
    payload = json.loads(_transform_sec(raw).decode("utf-8"))
    assert set(payload["mappings"].keys()) == {"X"}


def test_hkex_transform_parses_xlsx(tmp_path: Path):
    """Build a minimal xlsx with numeric stock codes in column A and confirm
    the transform produces the canonical 4-digit-padded HK ticker form
    (the rest of the codebase — fixtures, alias variants, treemap palettes —
    all uses `0700.HK`, not the leading-zero-stripped `700.HK`)."""
    pytest.importorskip("openpyxl")
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Stock Code", "Name"])
    ws.append(["00700", "Tencent"])
    ws.append(["09988", "Alibaba"])
    ws.append(["00001", "CKH"])
    ws.append(["60000", "Some-warrant"])
    ws.append(["text-not-numeric", "ignored"])
    out_path = tmp_path / "x.xlsx"
    wb.save(out_path)

    out = _transform_hkex(out_path.read_bytes())
    payload = json.loads(out.decode("utf-8"))
    assert payload["mappings"]["0700.HK"] == "00700"
    assert payload["mappings"]["9988.HK"] == "09988"
    assert payload["mappings"]["0001.HK"] == "00001"
    assert payload["mappings"]["60000.HK"] == "60000"


def test_hkex_transform_reads_full_sheet_despite_dimension_metadata(tmp_path: Path):
    """Regression for the `read_only=True` bug: HKEX's published xlsx ships
    with a stale worksheet `dimension` xml tag, and openpyxl's read-only mode
    honors that tag literally — truncating to the first few rows. The
    transform must therefore load the sheet in full (non-streaming) mode."""
    pytest.importorskip("openpyxl")
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Stock Code", "Name"])
    for i in range(1, 50):
        ws.append([f"{i:05d}", f"row-{i}"])
    out_path = tmp_path / "many.xlsx"
    wb.save(out_path)

    payload = json.loads(_transform_hkex(out_path.read_bytes()).decode("utf-8"))
    # Should produce one mapping per data row, not just the first handful.
    assert len(payload["mappings"]) == 49
