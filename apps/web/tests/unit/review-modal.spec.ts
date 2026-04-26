/**
 * Tasks 5.5 + 5.6: ReviewModal SSR smoke + JudgementList chip dispatch.
 *
 * Run with: pnpm test:unit
 */
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import * as React from "react";

// Stub next/navigation before importing modules that use useRouter().
const nextNavigationKey = require.resolve("next/navigation");
require.cache[nextNavigationKey] = {
  id: nextNavigationKey,
  filename: nextNavigationKey,
  loaded: true,
  exports: { useRouter: () => ({ refresh: () => {} }) },
} as NodeJS.Module;

// 1) ReviewModal closed by default (zustand initial state)
{
  const { ReviewModal } = require("../../components/ReviewModal");
  const html = renderToStaticMarkup(React.createElement(ReviewModal, null));
  assert.equal(html, "", "ReviewModal closed should render empty");
}

// 2) JudgementList without review renders a span (not clickable)
{
  const { JudgementList } = require("../../components/JudgementList");
  const judgement = {
    id: "j-test", rank: 1, level: "watch", level_label: "关注",
    title: "T", metadata: "m", evidence_count: 2,
    requires_review: false, review: null,
    no_direct_portfolio_link: false,
    reasoning_chain: { observed: "", portfolio_exposure: "", inference: "", conclusion: "" },
    evidence: [], supplementary_sources: [], suggested_questions: [],
  };
  const html = renderToStaticMarkup(React.createElement(JudgementList, { judgements: [judgement] }));
  assert.ok(html.includes("关注"), "level_label should appear");
  assert.ok(!html.includes('aria-label="复核详情'), "no review chip when review null");
}

// 3) JudgementList with open review renders clickable chip
{
  const { JudgementList } = require("../../components/JudgementList");
  const judgement = {
    id: "j-2", rank: 2, level: "elevated", level_label: "重点 · ⚠ 待复核",
    title: "Conflict case", metadata: "m", evidence_count: 4,
    requires_review: true,
    review: { reason: "source_conflict", note: "n", status: "open", reviewed_at: null },
    no_direct_portfolio_link: false,
    reasoning_chain: { observed: "", portfolio_exposure: "", inference: "", conclusion: "" },
    evidence: [], supplementary_sources: [], suggested_questions: [],
  };
  const html = renderToStaticMarkup(React.createElement(JudgementList, { judgements: [judgement] }));
  assert.ok(html.includes("⚠ 待复核"), "open review keeps original label");
  assert.ok(html.includes('aria-label="复核详情'), "review chip should be a button");
}

// 4) JudgementList with reviewed review shows "已审" suffix in muted color
{
  const { JudgementList } = require("../../components/JudgementList");
  const judgement = {
    id: "j-3", rank: 3, level: "elevated", level_label: "重点 · ⚠ 待复核",
    title: "Resolved case", metadata: "m", evidence_count: 4,
    requires_review: true,
    review: { reason: "source_conflict", note: "n", status: "reviewed", reviewed_at: "2026-04-26T08:00:00+08:00" },
    no_direct_portfolio_link: false,
    reasoning_chain: { observed: "", portfolio_exposure: "", inference: "", conclusion: "" },
    evidence: [], supplementary_sources: [], suggested_questions: [],
  };
  const html = renderToStaticMarkup(React.createElement(JudgementList, { judgements: [judgement] }));
  assert.ok(html.includes("✓ 已审"), "reviewed chip should show ✓ 已审");
  assert.ok(!html.includes("⚠ 待复核"), "reviewed chip should drop ⚠ 待复核 suffix");
}

console.log("review-modal: 4 cases OK");
