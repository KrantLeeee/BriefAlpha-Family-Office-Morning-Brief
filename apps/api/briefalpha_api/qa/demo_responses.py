"""Pre-baked QA responses for demo mode.

In demo mode the LLM is unavailable / unconfigured, but we still want
the UI's QA box to give the reviewer something to play with. This is a
small keyword-keyed lookup that returns a canned answer when the user
asks one of a handful of common-shape questions about the demo brief.

Reviewers see an explicit '示例回答' badge in the UI when this fires
(driven by failure_reason == 'demo_mode_prebaked').
"""
from __future__ import annotations

DEMO_TABLE: list[tuple[list[str], str]] = [
    (
        ["hi", "hello", "你好"],
        "👋 这是 BriefAlpha 的 demo 模式。你可以问：\n"
        "• 总结今日要点\n"
        "• NVDA 为什么是重点持仓？\n"
        "• 待复核 chip 是什么意思？",
    ),
    (
        ["总结", "摘要", "今日要点", "今日"],
        "今日 demo brief 的三条主要研判：\n"
        "(1) 英伟达盘后下调 Q1 数据中心营收指引 8-10%，触发 ⚠ 待复核\n"
        "(2) 腾讯扩大回购授权 50%（HKEX 公告），支撑港股互联网估值\n"
        "(3) Fed Williams 措辞 'mildly restrictive'，TLT 久期承压。",
    ),
    (
        ["nvda", "英伟达"],
        "NVDA 在 demo 组合中占 18%（核心持仓）。盘后股价跌约 6%；"
        "路透/彭博对下调幅度报告分歧（8% vs 10%），所以这条研判被标为 ⚠ 待复核。",
    ),
    (
        ["腾讯", "0700", "tencent", "buyback"],
        "0700.HK 在 demo 组合中占 15%。回购授权从 1000 亿提到 1500 亿港元，"
        "可作为港股互联网 thesis 的轻度正向信号。",
    ),
    (
        ["fed", "联储", "加息", "williams"],
        "Williams 在 NABE 会议措辞 'mildly restrictive'，市场理解为年内仍可能加息一次，"
        "对 TLT 等长久期资产形成压力。",
    ),
    (
        ["待复核", "复核", "review"],
        "「⚠ 待复核」表示此研判触发了人工复核条件。常见原因：来源对关键数字分歧、"
        "组合关联不明、阈值穿越。点击 chip 可看具体原因，并标记为已审。",
    ),
    (
        ["来源", "证据", "evidence", "链接"],
        "demo 模式下所有 evidence 链接以 'briefalpha://demo/' 开头，"
        "点击会弹窗显示完整引文，不会跳转外网。"
        "live 模式下 evidence 会带真实可点击的 URL。",
    ),
    (
        ["mode", "模式", "切换", "demo", "live"],
        "BriefAlpha 有 demo / live 两个模式。当前是 demo（默认）。"
        "切到 live 需要 export BRIEFALPHA_MODE=live + 配置 LLM key 和 SEC EDGAR user agent。"
        "详见 README 的『切换模式』章节。",
    ),
    (
        ["macro", "宏观", "脉搏", "宏观脉搏"],
        "宏观脉搏面板含 8 项指标：2Y UST / 10Y UST / DXY / VIX / WTI / Gold / USDCNH / HSI futures。"
        "demo 模式下数值是 fixture；live 模式连真实行情。",
    ),
]


def lookup(question: str) -> str | None:
    """Return a pre-baked answer if any keyword matches; otherwise None."""
    q = question.lower()
    for keywords, answer in DEMO_TABLE:
        if any(kw.lower() in q for kw in keywords):
            return answer
    return None
