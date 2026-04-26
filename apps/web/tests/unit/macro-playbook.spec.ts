/**
 * Tasks 6.1 + 6.2 + 6.3: MacroPulse expand & TodayPlaybook event evidence.
 *
 * SSR smoke only — interaction in Playwright E2E (Task 9.1).
 */
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import * as React from "react";
import { MacroPulseCollapsed } from "../../components/MacroPulseCollapsed";
import { MacroPulseExpanded } from "../../components/MacroPulseExpanded";
import { TodayPlaybook } from "../../components/TodayPlaybook";
import type { MacroPulseItem, PlaybookEvent, Judgement } from "../../lib/types";

const items: MacroPulseItem[] = [
  { name: "2Y UST", value: "4.61%", delta: "+6bp", threshold: "<4.50% benign", status: "watch" },
  { name: "VIX", value: "16.2", delta: "+0.9", threshold: "<20 benign", status: "ok" },
];

// Collapsed: shows label + expand affordance, hides items
{
  const html = renderToStaticMarkup(
    React.createElement(MacroPulseCollapsed, {
      label: "宏观脉搏 · 8 项指标",
      expandLabel: "展开 8 项指标",
      items,
    })
  );
  assert.ok(html.includes("宏观脉搏"), "label visible");
  assert.ok(html.includes("展开 8 项指标"), "expand affordance visible");
  assert.ok(!html.includes("2Y UST"), "items hidden when collapsed");
}

// Expanded view directly shows item rows
{
  const html = renderToStaticMarkup(React.createElement(MacroPulseExpanded, { items }));
  assert.ok(html.includes("2Y UST"), "first item rendered");
  assert.ok(html.includes("VIX"), "second item rendered");
  assert.ok(html.includes("4.61%"), "value rendered");
  assert.ok(html.includes("+6bp"), "delta rendered");
}

// Expanded with empty items: friendly fallback
{
  const html = renderToStaticMarkup(React.createElement(MacroPulseExpanded, { items: [] }));
  assert.ok(html.includes("暂无宏观脉搏数据"), "empty state rendered");
}

// TodayPlaybook with no related evidence on event: no toggle button
{
  const events: PlaybookEvent[] = [
    {
      time_hkt: "09:30",
      relative_time_hkt: "60 分钟后",
      label: "open",
      detail: "d",
      related_judgement_ids: ["j1"],
      related_evidence_ids: [],
      is_next: true,
    },
  ];
  const judgements: Judgement[] = [];
  const html = renderToStaticMarkup(React.createElement(TodayPlaybook, { events, judgements }));
  assert.ok(html.includes("09:30 HKT"), "event time visible");
  assert.ok(!html.includes("查看 "), "no '查看 N 条依据' affordance when no related evidence");
}

// TodayPlaybook with related evidence: shows the toggle button
{
  const events: PlaybookEvent[] = [
    {
      time_hkt: "09:30",
      relative_time_hkt: "60 分钟后",
      label: "open",
      detail: "d",
      related_judgement_ids: ["j1"],
      related_evidence_ids: ["ev_x"],
      is_next: true,
    },
  ];
  const judgements: Judgement[] = [
    {
      id: "j1", rank: 1, level: "watch", level_label: "关注",
      title: "T", metadata: "m", evidence_count: 1,
      requires_review: false, review: null,
      no_direct_portfolio_link: false,
      reasoning_chain: { observed: "", portfolio_exposure: "", inference: "", conclusion: "" },
      evidence: [
        {
          evidence_id: "ev_x",
          index_label: "①",
          source_label: "S",
          title: "Title",
          quote: "Q",
          source_link: "briefalpha://demo/ev_x",
          link_kind: "internal_demo",
        },
      ],
      supplementary_sources: [],
      suggested_questions: [],
    },
  ];
  const html = renderToStaticMarkup(React.createElement(TodayPlaybook, { events, judgements }));
  assert.ok(html.includes("查看 1 条依据"), "toggle visible with count");
  assert.ok(!html.includes("Title"), "evidence body hidden when collapsed");
}

console.log("macro-playbook: 5 cases OK");
