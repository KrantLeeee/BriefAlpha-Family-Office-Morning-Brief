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
    ok, _ = validate_numbers(
        answer_text="下调 8% 数据中心营收",
        excerpt_text="数据中心营收下调 8% 主因企业端需求趋缓",
    )
    assert ok

    ok, _ = validate_numbers(
        answer_text="下调 18% 数据中心营收",
        excerpt_text="数据中心营收下调 8% 主因企业端需求趋缓",
    )
    assert not ok


def test_numbers_ignores_unit_less_integers() -> None:
    """Production audit logs (2026-04-27) showed every stage_a/b rejection
    came from unit-less small integers (10, 11, 12) and stripped prices
    (424.62, 131.8) — narrative phrasing like "过去 12 个月" or a Chinese
    answer referring to a price the English excerpt wrote as `$424.62`.
    Unit-less terms must NOT participate in the substring check."""
    ok, _ = validate_numbers(
        answer_text="过去 12 个月内出现 3 次类似走势，参考第 5 季度的反弹模式",
        excerpt_text="The setup recurred 0 times historically.",
    )
    assert ok


def test_numbers_catches_unit_bearing_hallucinations() -> None:
    """The whole point of the validator: keep the strong constraint on
    explicit unit-bearing claims so 5%/8.4bp/3x fabrications still fail."""
    ok, reason = validate_numbers(
        answer_text="毛利率扩张 5%",
        excerpt_text="毛利率持稳，公司未给出指引。",
    )
    assert not ok and "5" in (reason or "")

    ok, _ = validate_numbers(
        answer_text="2 年期收益率上行 8bps",
        excerpt_text="2 年期收益率上行 8bps，市场重新定价加息路径。",
    )
    assert ok


def test_numbers_handles_currency_prefix_either_side() -> None:
    """`$424.62` (Western, prefix) must match the same number whether the
    answer writes `$424.62` or `424.62 美元` (Chinese, suffix)."""
    ok, _ = validate_numbers(
        answer_text="股价 424.62 美元",
        excerpt_text="Apple stock at $424.62 after the print.",
    )
    assert ok


def test_numbers_allows_market_price_rounding_from_unitless_excerpt() -> None:
    """yfinance excerpts carry prices as plain numbers. Chinese QA answers may
    add a currency unit and round long floats to two decimals; that is still
    grounded in the excerpt."""
    ok, reason = validate_numbers(
        answer_text="日内价格区间在 269.65 美元至 273.06 美元之间，收盘价 272.70 美元。",
        excerpt_text="AAPL 上次收盘 272.7; 日内 273.05999755859375 / 269.6499938964844; 成交量 38124500.",
    )
    assert ok, reason


def test_polarity_mismatch_flagged() -> None:
    ok, _ = validate_polarity(
        answer_text="腾讯 beat 预期", excerpt_text="腾讯 miss 预期"
    )
    assert not ok
    ok, _ = validate_polarity(
        answer_text="无方向描述", excerpt_text="也无方向"
    )
    assert ok
