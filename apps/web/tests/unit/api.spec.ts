/**
 * Unit-style assertion that the API client no longer silently falls back
 * to fixtures on error. The page (server component) and <ModeBanner>
 * surface the failure visibly — the client must propagate, not swallow.
 *
 * Run with:
 *   pnpm --filter @briefalpha/web test:unit:api
 */
import assert from "node:assert/strict";

async function run() {
  // Stub fetch with a 500 — getBriefToday should reject, not return a
  // fixture-derived Brief.
  (globalThis as Record<string, unknown>).fetch = async () =>
    new Response("boom", { status: 500 });

  const { getBriefToday, getSourceHealth } = await import("@/lib/api");

  await assert.rejects(
    () => getBriefToday(),
    /500/,
    "getBriefToday must reject on 500 (no silent fallback)"
  );

  await assert.rejects(
    () => getSourceHealth(),
    /500/,
    "getSourceHealth must reject on 500 (no silent fallback)"
  );

  let capturedInit: RequestInit | undefined;
  (globalThis as Record<string, unknown>).fetch = async (_url: string, init?: RequestInit) => {
    capturedInit = init;
    return new Response("{}", { status: 200 });
  };
  await getSourceHealth();
  assert.equal(
    new Headers(capturedInit?.headers).has("Content-Type"),
    false,
    "GET requests should not force Content-Type and trigger CORS preflight"
  );

  // Stub fetch with a network-level error — getBriefToday should still
  // reject (TypeError propagates), not absorb into a fixture.
  (globalThis as Record<string, unknown>).fetch = async () => {
    throw new TypeError("network");
  };

  await assert.rejects(
    () => getBriefToday(),
    /network|TypeError/,
    "getBriefToday must reject on network error (no silent fallback)"
  );

  // eslint-disable-next-line no-console
  console.log("api: getBriefToday + getSourceHealth propagate errors OK");
}

run().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});
