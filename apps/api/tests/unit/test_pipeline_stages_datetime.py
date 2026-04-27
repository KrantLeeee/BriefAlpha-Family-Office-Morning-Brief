from __future__ import annotations

from datetime import datetime, timezone

from briefalpha_api.pipeline.stages import Evidence, base_scoring


def test_base_scoring_accepts_sqlite_naive_datetimes() -> None:
    ev = Evidence(
        evidence_id="ev_naive",
        source_tier="research",
        source_name="research",
        source_reliability=0.5,
        title="Research chunk",
        excerpt="Persisted SQLite datetime should score.",
        quote_span=None,
        detected_tickers=[],
        chunk_type="text",
        asset_class=None,
        exposure_bucket=None,
        published_at=datetime(2026, 4, 27, 10, 0, 0),
        fetched_at=datetime(2026, 4, 27, 10, 0, 0),
    )

    scored = base_scoring(
        [ev],
        brief_freeze_at=datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert scored[0].score_breakdown["recency_weight"] == 1.0
    assert scored[0].base_score > 0
