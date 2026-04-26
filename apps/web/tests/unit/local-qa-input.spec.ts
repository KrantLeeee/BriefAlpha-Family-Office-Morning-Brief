/**
 * Task 4.4: LocalQaInput renders friendly text per failure_reason.
 *
 * SSR-only smoke; the interactive submit/fetch loop is covered by Task 9.1 E2E.
 *
 * Run with: pnpm test:unit
 */
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import * as React from "react";
import { LocalQaInput } from "../../components/LocalQaInput";

// Initial render — no response yet — placeholder visible
{
  const html = renderToStaticMarkup(
    React.createElement(LocalQaInput, {
      briefId: "2026-04-25",
      scope: "global",
      suggestedQuestions: ["a", "b"],
    })
  );
  assert.ok(html.includes("基于上方证据提问"), "input placeholder should render");
  assert.ok(html.includes("提问"), "submit button should render");
  assert.ok(html.includes("试试"), "suggested questions section should render");
}

console.log("local-qa-input: 1 case OK (initial render smoke)");
