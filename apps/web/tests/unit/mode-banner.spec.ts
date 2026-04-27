/**
 * Task 2.8: ModeBanner.
 *
 * Run with: pnpm test:unit (auto-wired into the npm script).
 */
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";
import { ModeBanner } from "../../components/ModeBanner";
import type { SystemMeta } from "../../lib/types";

const make = (overrides: Partial<SystemMeta> = {}): SystemMeta => ({
  mode: "live",
  status: "ready",
  generated_at: null,
  last_refreshed_at: null,
  data_quality: "live",
  ...overrides,
});

// Live + ready → renders nothing (null)
{
  const html = renderToStaticMarkup(React.createElement(ModeBanner, { system: make() }));
  assert.equal(html, "", "live+ready should render nothing");
}

// Demo mode → orange banner with tooltip hint (NO href, no anchor)
{
  const html = renderToStaticMarkup(
    React.createElement(ModeBanner, {
      system: make({ mode: "demo", data_quality: "fixture" }),
    })
  );
  assert.ok(html.includes("示例数据"), "demo banner should include 示例数据");
  assert.ok(html.includes("如何切到真实管线"), "demo banner should include the hint label");
  assert.ok(
    !html.includes("href"),
    "demo banner must NOT contain a hyperlink (Next has no /README route)",
  );
  assert.ok(
    html.includes("BRIEFALPHA_MODE=live"),
    "demo banner tooltip should mention how to switch",
  );
}

// Live + generating → blue banner, no hint
{
  const html = renderToStaticMarkup(
    React.createElement(ModeBanner, {
      system: make({ status: "generating", data_quality: "unavailable" }),
    })
  );
  assert.ok(html.includes("正在生成今日"), "generating banner should include the loading label");
  assert.ok(!html.includes("如何切到真实管线"), "generating banner should not show the demo hint");
}

// Live + stale → gray banner
{
  const html = renderToStaticMarkup(
    React.createElement(ModeBanner, { system: make({ status: "stale" }) })
  );
  assert.ok(html.includes("显示昨日数据"), "stale banner should include yesterday label");
}

// Live + error → red banner
{
  const html = renderToStaticMarkup(
    React.createElement(ModeBanner, { system: make({ status: "error" }) })
  );
  assert.ok(html.includes("数据获取失败"), "error banner should include failure label");
}

console.log("mode-banner: 5 cases OK");
