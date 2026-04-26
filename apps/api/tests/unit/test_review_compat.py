import pytest

from briefalpha_api.pipeline.artifact import derive_review


def test_compat_maps_requires_review_to_data_gap():
    raw = {"requires_review": True}
    assert derive_review(raw) == {
        "reason": "data_gap",
        "note": "",
        "status": "open",
        "reviewed_at": None,
    }


def test_compat_prefers_explicit_review_when_dict():
    raw = {
        "requires_review": True,
        "review": {
            "reason": "source_conflict",
            "note": "n",
            "status": "open",
            "reviewed_at": None,
        },
    }
    assert derive_review(raw)["reason"] == "source_conflict"


def test_compat_returns_none_when_neither_set():
    assert derive_review({"requires_review": False}) is None


def test_compat_returns_none_for_empty_raw():
    assert derive_review({}) is None


def test_compat_treats_explicit_none_review_as_no_override():
    # Explicit `review: None` should fall through to the requires_review check.
    raw = {"requires_review": True, "review": None}
    out = derive_review(raw)
    assert out is not None
    assert out["reason"] == "data_gap"
