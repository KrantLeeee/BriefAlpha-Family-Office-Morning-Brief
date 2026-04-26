/**
 * Task 6.4: EvidenceTrailDrawer SSR smoke.
 *
 * Drawer is closed by default (zustand initial state) and renders an
 * empty markup string in that case.
 */
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import * as React from "react";
import { EvidenceTrailDrawer } from "../../components/EvidenceTrailDrawer";

const html = renderToStaticMarkup(React.createElement(EvidenceTrailDrawer, null));
assert.equal(html, "", "EvidenceTrailDrawer closed should render empty");

console.log("evidence-trail-drawer: 1 case OK");
