import pydantic
import pytest

from briefalpha_api.pipeline.schemas import MacroPulseItem


def test_macro_pulse_item_minimal_payload():
    item = MacroPulseItem(
        name="2Y UST",
        value="4.61%",
        delta="+6bp",
        threshold="<4.50% benign",
        status="watch",
    )
    assert item.delta.startswith("+")
    assert item.status == "watch"


def test_macro_pulse_item_rejects_invalid_status():
    with pytest.raises(pydantic.ValidationError):
        MacroPulseItem(
            name="VIX",
            value="16",
            delta="0",
            threshold="<20 benign",
            status="critical",
        )
