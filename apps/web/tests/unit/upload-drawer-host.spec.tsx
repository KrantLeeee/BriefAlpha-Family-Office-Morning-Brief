/**
 * Upload drawer parse_report compatibility guards.
 *
 * Run with: pnpm test:unit
 */
import assert from "node:assert/strict";

import {
  isCompleteParseReport,
  isFailedParseReport,
} from "../../components/UploadDrawerHost";

assert.equal(
  isCompleteParseReport({
    status: "queued",
    filename: "queued.pdf",
    size_label: "1.0 MB",
    page_count: 0,
    uploaded_at_hkt: "16:00",
    parse_seconds: null,
    stages: [],
    tickers_in_universe: [],
    tickers_external: [],
    low_confidence_chunks: [],
  }),
  false,
  "queued parse_report must stay in loading state"
);

assert.equal(
  isCompleteParseReport({
    status: "ok",
    filename: "done.pdf",
    size_label: "1.0 MB",
    page_count: 1,
    uploaded_at_hkt: "16:01",
    parse_seconds: 1.2,
    stages: [{ name: "extraction", status: "ok", detail: "1 pages" }],
    tickers_in_universe: [],
    tickers_external: [],
    low_confidence_chunks: [],
  }),
  true,
  "completed parse_report should render the parsed panel"
);

assert.equal(
  isFailedParseReport({
    status: "failed",
    filename: "failed.pdf",
    size_label: "1.0 MB",
    page_count: 0,
    uploaded_at_hkt: "16:02",
    parse_seconds: null,
    stages: [],
    tickers_in_universe: [],
    tickers_external: [],
    low_confidence_chunks: [],
  }),
  true,
  "failed parse_report should render an error state"
);

console.log("upload-drawer-host: parse_report guards OK");
