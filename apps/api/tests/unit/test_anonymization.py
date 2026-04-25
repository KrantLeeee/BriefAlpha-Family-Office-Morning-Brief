"""Unit tests for the anonymization layer.

Covers task 3.9:
- 公司名漏出
- "Tencent" / "腾讯" map to the same alias
- Cross-exchange formats normalize to the same alias
- Whitelist field filtering on AliasedEvidence
- LLM-fabricated ticker is replaced (output scan) and not reverse-mapped
- Aliases without quote_span anchor are not reverse-mapped
"""
from __future__ import annotations

from briefalpha_api.anonymization.alias import make_alias_context
from briefalpha_api.anonymization.replace import (
    AliasedEvidence,
    aliased_to_original,
    build_aliased_evidence,
    replace_in_text,
)
from briefalpha_api.anonymization.reverse import reverse_alias
from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    build_sensitive_entity_dictionary,
)


def _ctx(tickers: list[str]):
    sd = build_sensitive_entity_dictionary(universe_tickers=tickers)
    return make_alias_context(
        brief_id="test_brief",
        universe_tickers=tickers,
        entity_dictionary=sd,
    )


def test_company_name_leak_is_replaced() -> None:
    ctx = _ctx(["NVDA"])
    out, segs = replace_in_text("英伟达盘后下调 Q1 指引", ctx, field="excerpt")
    assert "英伟达" not in out
    assert any(s.original_text == "英伟达" for s in segs)


def test_tencent_chinese_and_english_share_alias() -> None:
    ctx = _ctx(["0700.HK"])
    alias = ctx.alias_for("0700.HK")
    assert alias is not None
    out_zh, _ = replace_in_text("腾讯回购公告", ctx, field="excerpt")
    out_en, _ = replace_in_text("Tencent announced buyback", ctx, field="excerpt")
    assert alias in out_zh
    assert alias in out_en


def test_hk_exchange_format_variants_share_alias() -> None:
    ctx = _ctx(["0700.HK"])
    alias = ctx.alias_for("0700.HK")
    for variant in ("0700.HK", "00700.HK", "HKEX:00700", "HK:700"):
        assert ctx.alias_for(variant) == alias


def test_aliased_evidence_strips_unknown_fields() -> None:
    ev = AliasedEvidence(
        evidence_id="e1",
        title_aliased="t",
        excerpt_aliased="x",
        source_tier="news",
        # The following are NOT in the whitelist and must be silently dropped.
        secret_field="leak",  # type: ignore[call-arg]
    )  # type: ignore[call-arg]
    dump = ev.model_dump()
    assert "secret_field" not in dump


def test_quote_span_round_trip() -> None:
    ctx = _ctx(["NVDA"])
    excerpt = "英伟达盘后下调 Q1 数据中心指引 8%"
    target_substring = "数据中心指引 8%"
    o_start = excerpt.index(target_substring)
    o_end = o_start + len(target_substring)

    aliased, segs = build_aliased_evidence(
        evidence_id="e1",
        title="t",
        excerpt=excerpt,
        source_tier="news",
        asset_class="us_equity",
        published_at=None,
        ctx=ctx,
        quote_span_original=(o_start, o_end),
    )
    assert aliased.quote_span_aliased is not None
    mapped = aliased_to_original(aliased.quote_span_aliased, segs)
    # The reverse mapping recovers the original span exactly.
    assert mapped == (o_start, o_end)


def test_unsafe_generated_alias_is_redacted() -> None:
    ctx = _ctx(["NVDA"])
    fabricated_alias = "E_dead"
    out = reverse_alias(
        f"研判：{fabricated_alias} 风险升级",
        ctx,
        cited_evidence_excerpts_aliased=[],
    )
    assert fabricated_alias not in out.text
    assert "[redacted]" in out.text
    assert fabricated_alias in out.unsafe_generated_aliases


def test_alias_without_anchor_is_redacted_even_if_known() -> None:
    """Even valid aliases get redacted if not anchored in cited evidence."""
    ctx = _ctx(["NVDA"])
    real_alias = ctx.alias_for("NVDA")
    assert real_alias is not None
    out = reverse_alias(
        f"未引用的 {real_alias}",
        ctx,
        cited_evidence_excerpts_aliased=[],
    )
    assert real_alias not in out.text
    assert "[redacted]" in out.text


def test_alias_with_anchor_is_restored() -> None:
    ctx = _ctx(["NVDA"])
    real_alias = ctx.alias_for("NVDA")
    assert real_alias is not None
    out = reverse_alias(
        f"研判提到 {real_alias} 的指引下调",
        ctx,
        cited_evidence_excerpts_aliased=[f"…{real_alias} 盘后下调…"],
    )
    assert "NVDA" in out.text
    assert "[redacted]" not in out.text
