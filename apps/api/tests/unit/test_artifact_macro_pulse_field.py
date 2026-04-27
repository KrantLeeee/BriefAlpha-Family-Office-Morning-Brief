"""Regression: live brief artifact must always include `macro_pulse`.

The frontend TS type `Brief.macro_pulse: MacroPulseItem[]` is required;
without it `<MacroPulseExpanded>` crashes on `items.map(...)` once a live
brief is cached. The indicator pipeline isn't built yet, so we emit `[]` —
just enough to satisfy the contract.
"""
from __future__ import annotations

from briefalpha_api.pipeline.artifact import build_brief_artifact


def test_build_brief_artifact_emits_macro_pulse_field() -> None:
    pipeline_output = {
        "brief_id": "2026-04-26",
        "brief_date_hkt": "2026-04-26",
        "stage_a": None,
        "stage_b": None,
        "stage_c": None,
        "evidence_pool_full": [],
        "selected_evidence_for_llm": [],
        "no_direct_portfolio_link": False,
        "conservative": False,
    }
    artifact = build_brief_artifact(
        pipeline_output=pipeline_output,
        portfolio_positions=[],
        watchlist=[],
        source_health={"overall": "ok", "rows": []},
        quotes={},
        audit_mode="demo",
    )
    assert "macro_pulse" in artifact, "live artifact missing macro_pulse field"
    assert isinstance(artifact["macro_pulse"], list)
    # Pipeline-emitted artifacts should be empty until the indicator pipeline
    # is implemented; demo fixture supplies its own non-empty list.
    assert artifact["macro_pulse"] == []
    # Honesty: the collapsed label must reflect the actual indicator count,
    # not a hardcoded "8 项指标" lie. Earlier the label said 8 while the row
    # list was always empty — a fixture-mode dishonesty visible to live users.
    assert artifact["macro_pulse_collapsed"]["label"] == "宏观脉搏 · 暂未接入"
