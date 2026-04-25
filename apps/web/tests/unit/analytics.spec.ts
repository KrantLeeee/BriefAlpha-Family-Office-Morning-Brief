/**
 * Unit-style assertion that the analytics SDK preserves the
 * PRD §5.3 schema fields for `drawer_close` and `qa_response_render`.
 *
 * Run with:
 *   pnpm --filter @briefalpha/web exec tsx tests/unit/analytics.spec.ts
 */
import assert from "node:assert/strict";

import { track } from "@/lib/analytics";

declare const navigator: { sendBeacon?: (url: string, body: Blob) => boolean };

const captured: { url: string; body: string }[] = [];
(globalThis as { navigator?: typeof navigator }).navigator = {
  sendBeacon: (url: string, body: Blob) => {
    body.text().then((text) => captured.push({ url, body: text }));
    return true;
  },
};

track({
  event: "drawer_close",
  judgement_id: "j1",
  duration_ms: 4200,
  close_method: "esc",
});

track({
  event: "qa_response_render",
  judgement_id: "j1",
  cited_count: 2,
  validation_passed: true,
});

setTimeout(() => {
  assert.equal(captured.length >= 1, true, "events should be flushed via sendBeacon");
  const flat = captured.map((c) => c.body).join("");
  assert.match(flat, /"event":"drawer_close"/);
  assert.match(flat, /"duration_ms":4200/);
  assert.match(flat, /"close_method":"esc"/);
  assert.match(flat, /"event":"qa_response_render"/);
  assert.match(flat, /"cited_count":2/);
  assert.match(flat, /"validation_passed":true/);
  console.log("analytics: drawer_close + qa_response_render schema OK");
}, 600);
