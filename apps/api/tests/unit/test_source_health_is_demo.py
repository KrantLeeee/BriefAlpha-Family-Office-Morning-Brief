"""Task 7.1: aggregator stamps is_demo: False on rows."""
import pytest

from briefalpha_api.audit.source_health_aggregator import aggregate_source_health


@pytest.mark.asyncio
async def test_aggregate_source_health_research_row_marks_is_demo_false():
    snapshot = await aggregate_source_health()
    # The research row is always included; assert is_demo False on it.
    research_rows = [r for r in snapshot["rows"] if r.get("source_name") == "research"]
    assert research_rows, "expected at least the synthesized research row"
    assert all(r["is_demo"] is False for r in research_rows)
