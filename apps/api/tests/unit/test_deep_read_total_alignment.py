"""`deep_read.evidence_total` should reflect the brief's evidence base, not
the LLM citation count.

Before this change, when Stage A cited 2 evidence_ids the front page widget
read "证据轨迹 · 前 3 / 2" while the source-health table at the same
breakpoint reported 96+ raw items collected — making the trail look like
a fixture decoration instead of a window into the live evidence pool.
"""
from __future__ import annotations

from briefalpha_api.pipeline.artifact import _build_deep_read


def _ev(eid: str, tier: str) -> dict:
    return {
        "evidence_id": eid,
        "source_tier": tier,
        "source_name": tier,
        "title": f"{tier} {eid}",
        "excerpt": "x",
        "published_at": "2026-04-27T12:00:00",
        "raw_source_url": None,
    }


def test_evidence_total_reflects_selected_pool_not_just_citations() -> None:
    """Stage A cites 2 ids, but the brief is built on 20 selected rows.
    Surface 20 so the front page total aligns with what backs the brief."""
    selected = [_ev(f"e{i}", "news" if i < 5 else "market") for i in range(20)]
    full = selected + [_ev(f"r{i}", "research") for i in range(700)]

    result = _build_deep_read(
        selected=selected,
        full=full,
        stage_a={"cited_evidence_ids": ["e0", "e1"]},  # only 2 citations
        stage_b=None,
        stage_c=None,
    )

    assert result["evidence_total"] == 20, (
        "evidence_total should reflect the LLM-relevant selected pool, "
        "not the (often tiny) citation count"
    )
    # Trail rows still teaser top-3 of cited evidence — citation drives
    # the highlight, total drives the "查看全部 N" promise.
    assert len(result["evidence_trail"]) == 2  # only 2 cited ids exist


def test_evidence_total_falls_back_to_pool_size_when_no_selection() -> None:
    """Conservative path: nothing selected, no citations. Don't surface 0
    when the underlying pool actually has data — that misleads the user."""
    full = [_ev(f"e{i}", "news") for i in range(10)]
    result = _build_deep_read(
        selected=[],
        full=full,
        stage_a=None,
        stage_b=None,
        stage_c=None,
    )
    assert result["evidence_total"] == 10
