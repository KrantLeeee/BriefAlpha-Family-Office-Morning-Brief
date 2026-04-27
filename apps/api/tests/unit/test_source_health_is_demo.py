"""Task 7.1: aggregator stamps is_demo: False on rows."""
import pytest

from briefalpha_api.audit.source_health_aggregator import aggregate_source_health
from briefalpha_api.audit.source_health_aggregator import _research_detail


@pytest.mark.asyncio
async def test_aggregate_source_health_research_row_marks_is_demo_false():
    snapshot = await aggregate_source_health()
    # The research row is always included; assert is_demo False on it.
    research_rows = [r for r in snapshot["rows"] if r.get("source_name") == "research"]
    assert research_rows, "expected at least the synthesized research row"
    assert all(r["is_demo"] is False for r in research_rows)


def test_research_detail_keeps_completed_uploads_visible():
    assert (
        _research_detail(active_count=0, ready_count=2, chunk_count=256)
        == "2 uploads ready · 256 chunks"
    )
    assert (
        _research_detail(active_count=1, ready_count=2, chunk_count=256)
        == "1 uploads active · 2 uploads ready · 256 chunks"
    )
    assert _research_detail(active_count=0, ready_count=0, chunk_count=0) == "no uploads"
