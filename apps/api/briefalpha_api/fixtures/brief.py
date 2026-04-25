"""Hand-curated demo brief matching the Chinese canvas frames.

This fixture is the *contract* the frontend renders against. The live
pipeline (sections 2–14) will replace `get_demo_brief()` with the SQLite +
LLM-generated artifact, but the JSON shape MUST stay stable.
"""
from __future__ import annotations

from typing import Any


def get_demo_brief() -> dict[str, Any]:
    return {
        "brief_id": "2026-04-25",
        "brief_date_hkt": "2026-04-25",
        "delivered_at_hkt": "08:24",
        "freeze_window_hkt": "Apr 24 16:00 → Apr 25 08:30 HKT",
        "stale": False,
        "audit_mode": "demo",
        "anonymized": True,
        "no_direct_portfolio_link": False,
        "conservative": False,
        "degraded_sources": [],
        "base_case": {
            "headline_label": "今日核心判断",
            "headline": "英伟达下调 Q1 指引—30% 科技仓位需复核",
            "summary": (
                "英伟达盘后下调数据中心 Q1 营收"
                "指引约 8–10%，[1] 拖累美股科技 beta；"
                "腾讯扩大回购授权 50%，[2] 支撑港股"
                "互联网估值；联邦官员暗示年内或"
                "再加息，[3] 久期定价端面临压力。"
            ),
            "estimate_label": "隔夜估算",
            "estimate_value": "-1.09%",
            "estimate_direction": "down",
            "estimate_explainer": (
                "英伟达盘后指引下调拖累美股科技"
                "仓位；港股互联网吸收腾讯回购利好。"
            ),
            "evidence_count": 4,
        },
        "portfolio_snapshot": {
            "as_of_hkt": "2026-04-25 08:24",
            "tiles": [
                {
                    "ticker": "NVDA",
                    "weight_pct": "18.0%",
                    "change_pct": "-6.0%",
                    "trend": "down",
                    "color": "treemap.nvda",
                    "row": 0,
                    "col_start": 0,
                    "col_span": 209,
                },
                {
                    "ticker": "0700.HK",
                    "label": "0700",
                    "weight_pct": "15.0%",
                    "change_pct": "+2.4%",
                    "trend": "up",
                    "color": "treemap.tencent",
                    "row": 0,
                    "col_start": 209,
                    "col_span": 175,
                },
                {
                    "ticker": "AAPL",
                    "weight_pct": "12.0%",
                    "change_pct": "-1.6%",
                    "trend": "down",
                    "color": "treemap.aapl",
                    "row": 0,
                    "col_start": 384,
                    "col_span": 140,
                },
                {
                    "ticker": "MSFT",
                    "weight_pct": "10.0%",
                    "change_pct": "-0.8%",
                    "trend": "down",
                    "color": "treemap.msft",
                    "row": 0,
                    "col_start": 524,
                    "col_span": 116,
                },
                {
                    "ticker": "TLT",
                    "weight_pct": "10.0%",
                    "change_pct": "+0.3%",
                    "trend": "up",
                    "color": "treemap.tlt",
                    "row": 1,
                    "col_start": 0,
                    "col_span": 142,
                },
                {
                    "ticker": "9988.HK",
                    "label": "BABA",
                    "weight_pct": "8.0%",
                    "change_pct": "+1.1%",
                    "trend": "up",
                    "color": "treemap.baba",
                    "row": 1,
                    "col_start": 142,
                    "col_span": 114,
                },
                {
                    "ticker": "GLD",
                    "weight_pct": "8.0%",
                    "change_pct": "+0.4%",
                    "trend": "up",
                    "color": "treemap.gld",
                    "row": 1,
                    "col_start": 256,
                    "col_span": 114,
                },
                {
                    "ticker": "CASH",
                    "weight_pct": "9.0%",
                    "change_pct": "0.0%",
                    "trend": "flat",
                    "color": "treemap.cash",
                    "row": 1,
                    "col_start": 370,
                    "col_span": 128,
                },
                {
                    "ticker": "TSLA",
                    "weight_pct": "5.0%",
                    "change_pct": "-2.7%",
                    "trend": "down",
                    "color": "treemap.tsla",
                    "row": 1,
                    "col_start": 498,
                    "col_span": 71,
                },
                {
                    "ticker": "MTN",
                    "weight_pct": "5.0%",
                    "change_pct": "+0.6%",
                    "trend": "up",
                    "color": "treemap.mtn",
                    "row": 1,
                    "col_start": 569,
                    "col_span": 71,
                },
            ],
            "watchlist_summary": "AMD · GOOGL · 1810.HK · 未持有 · 仅作市场参照",
        },
        "judgements": [
            {
                "id": "j1",
                "rank": 1,
                "level": "elevated",
                "level_label": "重点 · ⚠ 待复核",
                "title": "英伟达下调 Q1 数据中心指引—重新评估超大规模算力链 thesis",
                "metadata": "SEC EDGAR 04-24 20:15 EDT · 4 来源 · NVDA 18% 核心持仓 · 路透 8% vs 彭博 10%—待复核",
                "evidence_count": 4,
                "requires_review": True,
                "no_direct_portfolio_link": False,
                "reasoning_chain": {
                    "observed": "英伟达盘后下调 Q1 数据中心营收指引约 8-10%；盘后股价跌 6%",
                    "portfolio_exposure": "NVDA 18% 核心持仓 + AI 算力链（MSFT/AAPL）约 22% 仓位",
                    "inference": "若超大规模厂商资本开支放缓，AI 算力链估值与英伟达同步重估",
                    "conclusion": "复核同主题持仓 thesis；来源对幅度有分歧（8% vs 10%）—需人工复核",
                },
                "evidence": [
                    {
                        "evidence_id": "ev_nvda_8k",
                        "index_label": "①",
                        "source_label": "SEC EDGAR · 04-24 20:15 EDT",
                        "title": "英伟达 8-K 指引更新",
                        "quote": "「…Q1 数据中心营收预期较前次指引下调约 8-10%，主因企业端需求趋缓与超大规模厂商库存正常化…」",
                        "source_link": "https://www.sec.gov/Archives/edgar/...",
                        "conflict": False,
                    },
                    {
                        "evidence_id": "ev_reuters_bbg",
                        "index_label": "②",
                        "source_label": "路透 vs 彭博 · ⚠ 冲突",
                        "title": "来源对下调幅度有分歧",
                        "quote": "路透：「英伟达下调 Q1 数据中心营收指引 8%」 · 彭博：「较一致预期下调约 10%」",
                        "source_link": "https://www.reuters.com/...",
                        "conflict": True,
                    },
                ],
                "supplementary_sources": [
                    {
                        "evidence_id": "ev_axios_recap",
                        "label": "Axios · 后续报道",
                        "source_link": "https://www.axios.com/...",
                    },
                    {
                        "evidence_id": "ev_yfinance_quote",
                        "label": "yfinance · 盘后报价",
                        "source_link": "yfinance://NVDA",
                    },
                ],
                "suggested_questions": [
                    "为什么报道的数字不同？",
                    "触发人工复核的阈值是什么？",
                ],
            },
            {
                "id": "j2",
                "rank": 2,
                "level": "watch",
                "level_label": "关注",
                "title": "腾讯扩大回购授权 50%，对港股互联网估值形成支撑",
                "metadata": "HKEX 07:30 HKT · 2 来源 · 0700.HK 15% 持仓 · 管理层信号",
                "evidence_count": 2,
                "requires_review": False,
                "no_direct_portfolio_link": False,
                "reasoning_chain": {
                    "observed": "腾讯公告扩大回购授权 50%，为 2024 以来最大幅度",
                    "portfolio_exposure": "0700.HK 15% 核心持仓 · 同港股互联网仓位共计约 23%",
                    "inference": "回购信号与股环估值估值反转一致",
                    "conclusion": "可作为港股互联网 thesis 的轻度正向信号；不需复核",
                },
                "evidence": [
                    {
                        "evidence_id": "ev_hkex_buyback",
                        "index_label": "①",
                        "source_label": "HKEX · 07:30 HKT",
                        "title": "腾讯控股回购授权公告",
                        "quote": "「董事会决议将 2026 年股份回购授权上限从 1,000 亿港元提高至 1,500 亿港元…」",
                        "source_link": "https://www1.hkexnews.hk/...",
                        "conflict": False,
                    },
                ],
                "supplementary_sources": [
                    {
                        "evidence_id": "ev_scmp_followup",
                        "label": "SCMP · 后续评论",
                        "source_link": "https://www.scmp.com/...",
                    },
                ],
                "suggested_questions": [
                    "回购节奏会如何影响包括 9988.HK 、 3690.HK 的同主题仓位？",
                ],
            },
            {
                "id": "j3",
                "rank": 3,
                "level": "watch",
                "level_label": "关注",
                "title": "Fed Williams 暗示年内或再加息一次，措辞 'mildly restrictive'",
                "metadata": "Fed RSS 04-24 14:00 EDT · 3 来源 · TLT 10% + 利率敏感 22% · 久期风险",
                "evidence_count": 3,
                "requires_review": False,
                "no_direct_portfolio_link": False,
                "reasoning_chain": {
                    "observed": "Williams 表示库存生产者价格预期仍偏高，未排除年内加息一次",
                    "portfolio_exposure": "TLT 10% + 利率敏感仓位共 22%",
                    "inference": "上言推升二年期收益率6bp；可能压缩 TLT 估值",
                    "conclusion": "关注今夜考虐诡 PCE 数据报告与上言一致性",
                },
                "evidence": [
                    {
                        "evidence_id": "ev_fed_williams_speech",
                        "index_label": "①",
                        "source_label": "Fed RSS · 04-24 14:00 EDT",
                        "title": "Williams 于 NABE 会议讲话",
                        "quote": "「Inflation may demand a mildly restrictive stance for some additional time...」",
                        "source_link": "https://www.federalreserve.gov/...",
                        "conflict": False,
                    },
                ],
                "supplementary_sources": [],
                "suggested_questions": [
                    "Williams 与 Powell 言论是否一致？",
                ],
            },
        ],
        "playbook_events": [
            {
                "time_hkt": "09:30",
                "relative_time_hkt": "60 分钟后",
                "label": "港股开盘——观察腾讯回购信号在港股互联网仓位的扩散",
                "detail": "关注 0700.HK / 9988.HK / 3690.HK 反应，确认回购是否支撑港股互联网",
                "related_judgement_ids": ["j2"],
                "is_next": True,
            },
            {
                "time_hkt": "21:30",
                "relative_time_hkt": "13 小时 06 分后",
                "label": "美股开盘——英伟达现金交易反应将定调今日科技 beta",
                "detail": "若指引下调外溢至 AI 算力链，超大规模相关持仓需进入今日复核",
                "related_judgement_ids": ["j1"],
                "is_next": False,
            },
        ],
        "deep_read": {
            "evidence_trail": [
                {"timestamp": "04-24 20:15 EDT", "label": "SEC EDGAR · 英伟达 8-K 指引"},
                {"timestamp": "07:30 HKT", "label": "HKEX · 腾讯回购公告"},
                {"timestamp": "04-24 14:00 EDT", "label": "Fed RSS · Williams 讲话"},
            ],
            "evidence_total": 20,
        },
        "macro_pulse_collapsed": {
            "label": "宏观脉搏 · 8 项指标",
            "expand_label": "展开 8 项指标",
        },
        "footer": {
            "left": "更新 08:24 HKT · 全部数据源正常",
            "right": "仅供信息支持，不构成投资建议。",
        },
    }


def get_demo_source_health() -> dict[str, Any]:
    return {
        "as_of_hkt": "08:24",
        "overall": "ok",
        "rows": [
            {"name": "行情", "status": "ok", "detail": "34 个标的"},
            {"name": "新闻", "status": "ok", "detail": "125 条"},
            {"name": "研报", "status": "active", "detail": "1 个上传"},
            {"name": "官方公告", "status": "ok", "detail": "10 条"},
        ],
    }


def get_demo_portfolio() -> dict[str, Any]:
    brief = get_demo_brief()
    return {
        "as_of_hkt": brief["portfolio_snapshot"]["as_of_hkt"],
        "tiles": brief["portfolio_snapshot"]["tiles"],
        "watchlist": [
            {"ticker": "AMD", "asset_class": "us_equity"},
            {"ticker": "GOOGL", "asset_class": "us_equity"},
            {"ticker": "1810.HK", "asset_class": "hk_equity"},
        ],
    }
