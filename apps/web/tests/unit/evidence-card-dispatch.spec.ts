/**
 * Task 3.2 + 3.3: EvidenceCard dispatches by link_kind, DemoEvidenceModal mounts.
 */
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import * as React from "react";
import { EvidenceCardItem } from "../../components/EvidenceCard";
import type { EvidenceCard } from "../../lib/types";

const base: EvidenceCard = {
  evidence_id: "ev_x",
  index_label: "①",
  source_label: "Source · Time",
  title: "Title",
  quote: "Q",
  source_link: "https://example.com",
  link_kind: "external",
  conflict: false,
};

// External: renders <a target=_blank>
{
  const html = renderToStaticMarkup(React.createElement(EvidenceCardItem, { card: base }));
  assert.ok(html.includes("<a "), "external should render <a>");
  assert.ok(html.includes('target="_blank"'), "external should be _blank");
  assert.ok(html.includes("查看原文"), "external label");
}

// internal_demo: renders <button>, no href
{
  const card = { ...base, link_kind: "internal_demo" as const, source_link: "briefalpha://demo/ev_x" };
  const html = renderToStaticMarkup(React.createElement(EvidenceCardItem, { card }));
  assert.ok(html.includes("<button"), "internal_demo should render <button>");
  assert.ok(!html.includes('target="_blank"'), "internal_demo should not be _blank");
  assert.ok(html.includes("示例 evidence"), "internal_demo label");
}

// internal_research: renders <button>
{
  const card = { ...base, link_kind: "internal_research" as const, source_link: "research://abc" };
  const html = renderToStaticMarkup(React.createElement(EvidenceCardItem, { card }));
  assert.ok(html.includes("<button"), "internal_research should render <button>");
  assert.ok(html.includes("内部研报"), "internal_research label");
}

// unavailable: renders <div>, not interactive
{
  const card = { ...base, link_kind: "unavailable" as const, source_link: undefined };
  const html = renderToStaticMarkup(React.createElement(EvidenceCardItem, { card }));
  assert.ok(!html.includes("<a "), "unavailable should not have <a>");
  assert.ok(!html.includes("<button"), "unavailable should not have <button>");
  assert.ok(html.includes("原文链接不可用"), "unavailable label");
  assert.ok(html.includes("cursor-not-allowed"), "unavailable disabled style");
}

console.log("evidence-card-dispatch: 4 cases OK");
