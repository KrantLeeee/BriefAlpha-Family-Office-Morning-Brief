from typing import get_args

import pydantic
import pytest

from briefalpha_api.pipeline.schemas import LinkKind, ReviewMeta


def test_review_meta_minimal_payload():
    rm = ReviewMeta(reason="source_conflict")
    assert rm.note == ""
    assert rm.status == "open"
    assert rm.reviewed_at is None


def test_review_meta_full_payload():
    rm = ReviewMeta(
        reason="data_gap",
        note="missing FX feed",
        status="reviewed",
        reviewed_at="2026-04-26T08:00:00+08:00",
    )
    assert rm.status == "reviewed"


def test_review_meta_rejects_invalid_reason():
    with pytest.raises(pydantic.ValidationError):
        ReviewMeta(reason="other")


def test_review_meta_rejects_invalid_status():
    with pytest.raises(pydantic.ValidationError):
        ReviewMeta(reason="data_gap", status="closed")


def test_link_kind_is_literal_alias():
    assert set(get_args(LinkKind)) == {
        "external",
        "internal_demo",
        "internal_research",
        "unavailable",
    }
