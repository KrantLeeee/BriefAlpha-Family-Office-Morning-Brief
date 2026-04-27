/**
 * Task 2.10: RefreshButton interaction smoke test.
 *
 * Run with: pnpm test:unit (auto-wired into the npm script).
 */
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";
import { createRequire } from "node:module";

// Stub `next/navigation` so `useRouter()` doesn't blow up under bare
// SSR without an app router (matches analytics.spec.ts pattern of
// stubbing globals before importing the module under test).
const require = createRequire(__filename);
const navigationPath = require.resolve("next/navigation");
require.cache[navigationPath] = {
  id: navigationPath,
  filename: navigationPath,
  loaded: true,
  exports: {
    useRouter: () => ({ refresh: () => undefined }),
  },
} as unknown as NodeJS.Module;

import("../../components/RefreshButton").then(({ RefreshButton }) => {
  // Initial render shows the default label.
  const html = renderToStaticMarkup(React.createElement(RefreshButton, null));
  assert.ok(html.includes("更新今日简报"), "default label should be 更新今日简报");
  assert.ok(html.includes("aria-label=\"更新今日简报\""), "should have aria-label");

  console.log("refresh-button: render smoke OK");
});
