"""Validator unit tests."""
from __future__ import annotations

from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    SensitiveEntityDictionary,
)
from briefalpha_api.validator.citations import validate_citations
from briefalpha_api.validator.numbers import validate_numbers
from briefalpha_api.validator.polarity import validate_polarity


def test_stage_a_requires_two_citations() -> None:
    ok, reason = validate_citations(
        structured={"cited_evidence_ids": ["e1"]}, pool_ids={"e1", "e2"}, scope="stage_a"
    )
    assert not ok and "fewer_than_2_citations" in (reason or "")


def test_numbers_must_appear_in_excerpt() -> None:
    ok, reason = validate_numbers(
        answer_text="下调 8% 数据中心营收",
        excerpt_text="数据中心营收下调 8% 主因企业端需求趋缓",
    )
    assert ok

    ok, reason = validate_numbers(
        answer_text="下调 18% 数据中心营收",
        excerpt_text="数据中心营收下调 8% 主因企业端需求趋缓",
    )
    assert not ok


def test_polarity_mismatch_flagged() -> None:
    ok, _ = validate_polarity(
        answer_text="腾讯 beat 预期", excerpt_text="腾讯 miss 预期"
    )
    assert not ok
    ok, _ = validate_polarity(
        answer_text="无方向描述", excerpt_text="也无方向"
    )
    assert ok
