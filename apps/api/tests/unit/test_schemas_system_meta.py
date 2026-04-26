import pytest
from briefalpha_api.pipeline.schemas import SystemMeta


def test_system_meta_required_fields():
    meta = SystemMeta(
        mode="demo",
        status="ready",
        generated_at=None,
        last_refreshed_at=None,
        data_quality="fixture",
    )
    assert meta.mode == "demo"
    assert meta.data_quality == "fixture"


def test_system_meta_rejects_invalid_mode():
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        SystemMeta(mode="staging", status="ready", data_quality="live")
