"""Convert pipeline output → frontend `Brief` shape.

The frontend (`apps/web/lib/types.ts:Brief`) is the contract: every key
this builder emits must exist in that type. When the live LLM is offline
or the pipeline degrades, we still produce a valid Brief so the UI never
breaks — degraded fields fall back to safe stubs.

Layout note: portfolio_snapshot tiles use an absolute layout that mirrors
`docs/Designs/BriefAlpha.pen` frame `fFOSV`. We hardcode the 10 demo
ticker positions so the visual stays pixel-faithful with the canvas;
generic treemap layout for arbitrary portfolios is a later concern.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")

# (col_start, col_span, row, color_token) — sourced from frame fFOSV's `tree`.
_LAYOUT: dict[str, tuple[int, int, int, str, str | None]] = {
    "NVDA":     (  0, 209, 0, "treemap.nvda",    None),
    "0700.HK":  (209, 175, 0, "treemap.tencent", "0700"),
    "AAPL":     (384, 140, 0, "treemap.aapl",    None),
    "MSFT":     (524, 116, 0, "treemap.msft",    None),
    "TLT":      (  0, 142, 1, "treemap.tlt",     None),
    "9988.HK":  (142, 114, 1, "treemap.baba",    "BABA"),
    "GLD":      (256, 114, 1, "treemap.gld",     None),
    "CASH":     (370, 128, 1, "treemap.cash",    None),
    "TSLA":     (498,  71, 1, "treemap.tsla",    None),
    "MTN":      (569,  71, 1, "treemap.mtn",     None),
}

LEVEL_LABEL = {
    "elevated": "重点",
    "watch": "关注",
    "info": "提示",
}


def classify_link_kind(url: str | None) -> str:
    """Map a raw evidence URL to one of the four LinkKind values.

    The frontend uses link_kind to decide click behavior:
      external          → open in new tab
      internal_demo     → open in-app modal explaining "fixture content"
      internal_research → route to /research/<id>
      unavailable       → render as disabled
    """
    if not url or url == "#":
        return "unavailable"
    if url.startswith("briefalpha://demo/"):
        return "internal_demo"
    if url.startswith("research://"):
        return "internal_research"
    if url.startswith(("http://", "https://")):
        return "external"
    return "unavailable"


def public_source_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("yfinance://"):
        ticker = url.removeprefix("yfinance://").strip()
        if ticker:
            return f"https://finance.yahoo.com/quote/{ticker}"
    return url


def build_brief_artifact(
    *,
    pipeline_output: dict[str, Any],
    portfolio_positions: list[dict[str, Any]],
    watchlist: list[str],
    source_health: dict[str, Any],
    quotes: dict[str, dict[str, Any]] | None = None,
    delivered_at_hkt: datetime | None = None,
    freeze_window_hkt: str = "Apr 24 16:00 → Apr 25 08:30 HKT",
    audit_mode: str = "demo",
) -> dict[str, Any]:
    """Build a frontend-shaped Brief.

    `pipeline_output` is whatever `pipeline.run.run_full_brief()` produced:
    it has `stage_a` / `stage_b` / `stage_c` (each may be `None` if the
    LLM was unavailable), `evidence_pool_full`, `selected_evidence_for_llm`,
    `no_direct_portfolio_link`, `conservative`.
    """
    delivered_at_hkt = delivered_at_hkt or datetime.now(tz=HKT)
    delivered_label = delivered_at_hkt.strftime("%H:%M")
    quotes = quotes or {}

    selected = pipeline_output.get("selected_evidence_for_llm", [])
    pool = pipeline_output.get("evidence_pool_full", [])

    base_case = _build_base_case(
        stage_a=pipeline_output.get("stage_a"),
        portfolio_positions=portfolio_positions,
        quotes=quotes,
    )
    portfolio_snapshot = _build_portfolio_snapshot(
        positions=portfolio_positions,
        watchlist=watchlist,
        quotes=quotes,
        delivered_at_hkt=delivered_at_hkt,
    )
    judgements = _build_judgements(
        stage_b=pipeline_output.get("stage_b"),
        evidence_pool=pool,
    )
    playbook_events = _build_playbook_events(
        stage_c=pipeline_output.get("stage_c"),
        stage_b=pipeline_output.get("stage_b"),
    )
    deep_read = _build_deep_read(selected=selected, full=pool)
    degraded_sources = [
        row["name"]
        for row in source_health.get("rows", [])
        if row.get("status") in {"degraded", "failed"}
    ]
    footer_left = _footer_left(delivered_label, source_health)

    macro_pulse: list[dict[str, Any]] = []
    macro_collapsed = _build_macro_collapsed(macro_pulse)
    return {
        "brief_id": pipeline_output["brief_id"],
        "brief_date_hkt": pipeline_output.get("brief_date_hkt", pipeline_output["brief_id"]),
        "delivered_at_hkt": delivered_label,
        "freeze_window_hkt": freeze_window_hkt,
        "stale": False,
        "audit_mode": audit_mode,
        "anonymized": True,
        "no_direct_portfolio_link": pipeline_output.get("no_direct_portfolio_link", False),
        "conservative": pipeline_output.get("conservative", False),
        "degraded_sources": degraded_sources,
        "base_case": base_case,
        "portfolio_snapshot": portfolio_snapshot,
        "judgements": judgements,
        "playbook_events": playbook_events,
        "deep_read": deep_read,
        "macro_pulse_collapsed": macro_collapsed,
        # The TS contract (`apps/web/lib/types.ts:Brief.macro_pulse`) requires this
        # field. The indicator pipeline isn't implemented yet, so we emit an
        # empty list and the collapsed label says so honestly (see
        # `_build_macro_collapsed`).
        "macro_pulse": macro_pulse,
        "footer": {"left": footer_left, "right": "仅供信息支持，不构成投资建议。"},
    }


def _build_macro_collapsed(macro_pulse: list[dict[str, Any]]) -> dict[str, str]:
    """Honest collapsed-row label. Earlier the label hard-coded "8 项指标"
    while the row list was always empty, which read as a fixture lie when
    the user expanded it. With no indicators we say so; with N indicators
    we count the actual N."""
    n = len(macro_pulse)
    if n == 0:
        return {"label": "宏观脉搏 · 暂未接入", "expand_label": "—"}
    return {"label": f"宏观脉搏 · {n} 项指标", "expand_label": f"展开 {n} 项指标"}


# ---------------------------------------------------------------------------
# base_case
# ---------------------------------------------------------------------------


def _build_base_case(
    *,
    stage_a: dict[str, Any] | None,
    portfolio_positions: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    overnight_pct, direction = _portfolio_overnight(portfolio_positions, quotes)
    headline = (stage_a or {}).get("base_case_headline") or "暂无核心判断（pipeline 已生成，等待 LLM 接入）"
    summary = (stage_a or {}).get("summary") or "等待 LLM 输出 base_case 摘要；当前 stub 模式。"
    cited = (stage_a or {}).get("cited_evidence_ids") or []
    return {
        "headline_label": "今日核心判断",
        "headline": headline,
        "summary": summary,
        "estimate_label": "隔夜估算",
        "estimate_value": f"{overnight_pct:+.2f}%",
        "estimate_direction": direction,
        "estimate_explainer": _explainer_from_overnight(direction, overnight_pct),
        "evidence_count": max(len(cited), 1),
    }


def _portfolio_overnight(
    positions: list[dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
) -> tuple[float, str]:
    weighted = 0.0
    total_weight = 0.0
    for pos in positions:
        q = quotes.get(pos["ticker"], {})
        ch = q.get("change_pct")
        if ch is None:
            continue
        weighted += ch * pos["weight"]
        total_weight += pos["weight"]
    pct = (weighted / total_weight) if total_weight else 0.0
    if pct > 0.0:
        return pct, "up"
    if pct < 0.0:
        return pct, "down"
    return pct, "flat"


def _explainer_from_overnight(direction: str, pct: float) -> str:
    if direction == "down":
        return "美股科技仓位拖累；港股互联网部分对冲。"
    if direction == "up":
        return "权重最大持仓表现稳健；防御性仓位配合。"
    return "隔夜整体平衡，无单一驱动主导。"


# ---------------------------------------------------------------------------
# portfolio_snapshot
# ---------------------------------------------------------------------------


def _build_portfolio_snapshot(
    *,
    positions: list[dict[str, Any]],
    watchlist: list[str],
    quotes: dict[str, dict[str, Any]],
    delivered_at_hkt: datetime,
) -> dict[str, Any]:
    tiles: list[dict[str, Any]] = []
    weight_total = sum(p["weight"] for p in positions) or 1.0
    for pos in positions:
        layout = _LAYOUT.get(pos["ticker"])
        if layout is None:
            continue
        col_start, col_span, row, color, display_label = layout
        q = quotes.get(pos["ticker"], {})
        change_pct = q.get("change_pct")
        if change_pct is None:
            change_label = "0.0%"
            trend = "flat"
        else:
            change_label = f"{change_pct:+.1f}%"
            trend = "up" if change_pct > 0 else "down" if change_pct < 0 else "flat"
        tile: dict[str, Any] = {
            "ticker": pos["ticker"],
            "weight_pct": f"{(pos['weight'] / weight_total) * 100:.1f}%",
            "change_pct": change_label,
            "trend": trend,
            "color": color,
            "row": row,
            "col_start": col_start,
            "col_span": col_span,
        }
        if display_label:
            tile["label"] = display_label
        tiles.append(tile)

    if not watchlist:
        watchlist_summary = "无关注列表"
    else:
        watchlist_summary = " · ".join(watchlist) + " · 未持有 · 仅作市场参照"

    return {
        "as_of_hkt": delivered_at_hkt.strftime("%Y-%m-%d %H:%M"),
        "tiles": tiles,
        "watchlist_summary": watchlist_summary,
    }


# ---------------------------------------------------------------------------
# judgements
# ---------------------------------------------------------------------------


def _build_judgements(
    *,
    stage_b: dict[str, Any] | None,
    evidence_pool: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not stage_b or not stage_b.get("judgements"):
        return []
    pool_index = {e["evidence_id"]: e for e in evidence_pool}
    out: list[dict[str, Any]] = []
    for raw in stage_b["judgements"]:
        cited = raw.get("cited_evidence_ids", [])
        evidence_cards = []
        for idx, eid in enumerate(cited, start=1):
            ev = pool_index.get(eid)
            if not ev:
                continue
            evidence_cards.append(_build_evidence_card(ev, idx))
        supplementary = []
        for ev in evidence_pool:
            if ev["evidence_id"] in cited:
                continue
            sup = ev.get("supplementary_sources") or []
            for s in sup[:1]:
                url = public_source_url(s.get("url")) or ""
                supplementary.append(
                    {
                        "evidence_id": ev["evidence_id"],
                        "label": s.get("source_name") or "辅助来源",
                        "source_link": url,
                        "link_kind": classify_link_kind(url),
                    }
                )
        out.append(
            {
                "id": f"j{raw.get('rank', len(out) + 1)}",
                "rank": raw.get("rank", len(out) + 1),
                "level": raw.get("level", "watch"),
                "level_label": _level_label(raw.get("level", "watch"), raw.get("requires_review", False)),
                "title": raw.get("title", "未命名研判"),
                "metadata": _judgement_metadata(raw, evidence_cards),
                "evidence_count": len(cited),
                "requires_review": bool(raw.get("requires_review")),
                "review": derive_review(raw),
                "no_direct_portfolio_link": bool(raw.get("no_direct_portfolio_link")),
                "reasoning_chain": raw.get("reasoning_chain", {}),
                "evidence": evidence_cards,
                "supplementary_sources": supplementary[:3],
                "suggested_questions": _suggested_questions(raw),
            }
        )
    return out


def derive_review(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Map legacy `requires_review: bool` onto the structured `review` dict.

    Explicit `review` dicts win; otherwise a truthy `requires_review` yields a
    default `data_gap` open review; everything else returns None.
    """
    review = raw.get("review")
    if isinstance(review, dict):
        return review
    if raw.get("requires_review"):
        return {"reason": "data_gap", "note": "", "status": "open", "reviewed_at": None}
    return None


def _level_label(level: str, requires_review: bool) -> str:
    base = LEVEL_LABEL.get(level, "关注")
    if requires_review:
        return f"{base} · ⚠ 待复核"
    return base


def _judgement_metadata(raw: dict[str, Any], evidence_cards: list[dict[str, Any]]) -> str:
    sources = ", ".join({c.get("source_label", "").split(" · ")[0] for c in evidence_cards if c.get("source_label")})
    cited_n = len(evidence_cards)
    bits = [
        sources or "多源",
        f"{cited_n} 来源",
    ]
    if raw.get("no_direct_portfolio_link"):
        bits.append("组合关联缺失")
    if raw.get("requires_review"):
        bits.append("⚠ 待复核")
    return " · ".join(bits)


def _suggested_questions(raw: dict[str, Any]) -> list[str]:
    qs = raw.get("suggested_questions") or []
    if qs:
        return qs[:3]
    base = ["为什么这条研判触发了？"]
    if raw.get("requires_review"):
        base.append("人工复核的阈值是什么？")
    return base


def _build_evidence_card(ev: dict[str, Any], idx: int) -> dict[str, Any]:
    circled = "①②③④⑤⑥⑦⑧⑨⑩"
    label = circled[idx - 1] if 1 <= idx <= len(circled) else f"({idx})"
    source_tier = ev.get("source_tier", "news")
    source_name = ev.get("source_name", "")
    pub = ev.get("published_at") or ""
    pub_label = pub[:16] if isinstance(pub, str) else ""
    url = public_source_url(ev.get("raw_source_url") or ev.get("source_link")) or "#"
    return {
        "evidence_id": ev["evidence_id"],
        "index_label": label,
        "source_label": " · ".join(filter(None, [source_name or source_tier, pub_label])),
        "title": ev.get("title", ""),
        "quote": ev.get("excerpt", ""),
        "source_link": url,
        "link_kind": classify_link_kind(url),
        "conflict": bool(ev.get("conflict")),
    }


# ---------------------------------------------------------------------------
# playbook_events
# ---------------------------------------------------------------------------


def _build_playbook_events(
    *,
    stage_c: dict[str, Any] | None,
    stage_b: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not stage_c or not stage_c.get("playbook_events"):
        return []
    judgement_evidence: dict[str, list[str]] = {}
    for raw in (stage_b or {}).get("judgements", []) or []:
        jid = f"j{raw.get('rank', len(judgement_evidence) + 1)}"
        judgement_evidence[jid] = list(raw.get("cited_evidence_ids") or [])
    events = sorted(
        stage_c["playbook_events"],
        key=lambda ev: _playbook_sort_key(ev.get("time_hkt", "全天")),
    )
    out = []
    for idx, ev in enumerate(events):
        related_judgement_ids = ev.get("related_judgement_ids", [])
        related_evidence_ids = list(ev.get("related_evidence_ids", []))
        if not related_evidence_ids:
            for jid in related_judgement_ids:
                related_evidence_ids.extend(judgement_evidence.get(jid, []))
        out.append(
            {
                "time_hkt": ev.get("time_hkt", "00:00"),
                "relative_time_hkt": ev.get("relative_time_hkt", ""),
                "label": ev.get("label", ""),
                "detail": ev.get("detail", ""),
                "related_judgement_ids": related_judgement_ids,
                "related_evidence_ids": list(dict.fromkeys(related_evidence_ids)),
                "is_next": idx == 0,
            }
        )
    return out


def _playbook_sort_key(time_label: str) -> tuple[int, int]:
    """Sort same-day Beijing-time event labels from morning to evening.

    The wire field is still named `time_hkt` for compatibility. HKT and BJT
    are both UTC+8, so the value is already Beijing clock time; the frontend
    labels it as BJT/北京时间.
    """
    if time_label == "全天":
        return (-1, 0)
    try:
        hh, mm = time_label.split(":", 1)
        hour = max(0, min(23, int(hh)))
        minute = max(0, min(59, int(mm)))
        return (hour, minute)
    except (ValueError, AttributeError):
        return (99, 0)


# ---------------------------------------------------------------------------
# deep_read
# ---------------------------------------------------------------------------


def _build_deep_read(
    *,
    selected: list[dict[str, Any]],
    full: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for ev in selected[:3]:
        pub = ev.get("published_at") or ""
        ts = pub[:16] if isinstance(pub, str) else ""
        rows.append(
            {
                "timestamp": ts,
                "label": f"{ev.get('source_name', '')} · {ev.get('title', '')[:40]}",
                "source_link": public_source_url(ev.get("raw_source_url")),
                "link_kind": classify_link_kind(public_source_url(ev.get("raw_source_url"))),
            }
        )
    return {
        "evidence_trail": rows,
        "evidence_total": len(full),
    }


# ---------------------------------------------------------------------------
# footer
# ---------------------------------------------------------------------------


def _footer_left(delivered_label: str, source_health: dict[str, Any]) -> str:
    overall = source_health.get("overall", "ok")
    if overall == "ok":
        return f"更新 {delivered_label} HKT · 全部数据源正常"
    return f"更新 {delivered_label} HKT · 数据源 degraded"
