import pydantic
import pytest

from briefalpha_api.pipeline.schemas import SystemMeta


def test_system_meta_required_fields():
    meta = SystemMeta(
        mode="demo",
        status="ready",
        data_quality="fixture",
    )
    assert meta.mode == "demo"
    assert meta.data_quality == "fixture"
    assert meta.generated_at is None
    assert meta.last_refreshed_at is None


def test_system_meta_rejects_invalid_mode():
    with pytest.raises(pydantic.ValidationError):
        SystemMeta(mode="staging", status="ready", data_quality="live")
