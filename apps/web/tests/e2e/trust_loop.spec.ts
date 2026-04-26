import { expect, test } from "@playwright/test";

/**
 * Task 9.1 — Trust loop happy path E2E.
 *
 * Exercises the user-facing trust loop end to end against a live demo
 * stack:
 *   1. ModeBanner shows "示例数据" in demo mode
 *   2. RefreshButton triggers /api/admin/data/refresh and surfaces a
 *      "已刷新 HH:MM" receipt
 *   3. Clicking a "⚠ 待复核" chip opens ReviewModal with reason + note
 *      and "我已审阅" persists via /api/review/{id}
 *   4. DeepRead "查看全部 N 条原文" opens the EvidenceTrailDrawer
 *   5. QA box answers the demo prompt "hi" with "示例回答" badge visible
 *   6. SourceHealth rows render the (示例) suffix
 *
 * Pre-reqs:
 *   - apps/api running with BRIEFALPHA_MODE=demo (the default).
 *     `make dev-api` from the repo root works.
 *   - Web server is auto-started by playwright.config.ts webServer block.
 *
 * Run: `cd apps/web && pnpm test:e2e -- trust_loop.spec.ts`
 */
test.describe("BriefAlpha — trust loop happy path (demo mode)", () => {
  test("ModeBanner shows the demo banner with switching-modes link", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("示例数据")).toBeVisible();
    await expect(page.getByRole("link", { name: /如何切到真实管线/ })).toBeVisible();
  });

  test("RefreshButton triggers refresh and shows the receipt", async ({ page }) => {
    await page.goto("/");
    const button = page.getByRole("button", { name: "刷新数据" });
    await expect(button).toBeVisible();

    // Watch the POST to confirm it actually fires.
    const refreshPromise = page.waitForResponse(
      (r) => r.url().includes("/api/admin/data/refresh") && r.request().method() === "POST",
    );
    await button.click();
    const resp = await refreshPromise;
    expect(resp.ok()).toBeTruthy();

    // After router.refresh() the label switches to "已刷新 HH:MM" or "已排队".
    await expect(button).toHaveText(/已刷新 \d{2}:\d{2}|已排队/);
  });

  test("review chip opens ReviewModal with reason and 我已审阅 button", async ({ page }) => {
    await page.goto("/");

    // The chip is the level_label button on a judgement that has review !== null.
    // In demo fixture, j1 (NVDA) has review.reason="source_conflict".
    const chip = page.getByRole("button", { name: /复核详情/ }).first();
    await expect(chip).toBeVisible();
    await chip.click();

    const dialog = page.getByRole("dialog", { name: /复核/ });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("触发原因")).toBeVisible();
    await expect(dialog.getByText("来源对关键数字分歧")).toBeVisible(); // source_conflict label
    await expect(dialog.getByRole("button", { name: /我已审阅/ })).toBeVisible();

    // Click "我已审阅" — POSTs to /api/review/{id} and refreshes
    const reviewPromise = page.waitForResponse(
      (r) => r.url().includes("/api/review/") && r.request().method() === "POST",
    );
    await dialog.getByRole("button", { name: /我已审阅/ }).click();
    const resp = await reviewPromise;
    expect(resp.ok()).toBeTruthy();

    // After refresh, the chip should now show "✓ 已审"
    await expect(page.getByText(/✓ 已审/)).toBeVisible();
  });

  test("DeepRead 查看全部 opens the evidence trail drawer", async ({ page }) => {
    await page.goto("/");

    const button = page.getByRole("button", { name: /查看全部.*条原文/ });
    await expect(button).toBeVisible();
    await button.click();

    const drawer = page.getByRole("dialog", { name: "证据轨迹" });
    await expect(drawer).toBeVisible();

    // Demo mode stamps source_tier="demo" so a "demo" filter chip is rendered.
    await expect(drawer.getByRole("button", { name: "demo" })).toBeVisible();
  });

  test("QA box returns prebaked '示例回答' for 'hi'", async ({ page }) => {
    await page.goto("/");

    // Open the first judgement drawer to access the LocalQaInput.
    const row = page.locator('[id^="judgement-row-"]').first();
    await row.click();

    const drawer = page.getByRole("dialog", { name: /研判.*详情/ });
    await expect(drawer).toBeVisible();

    const input = drawer.getByPlaceholder(/基于上方证据提问/);
    await input.fill("hi");
    const qaPromise = page.waitForResponse(
      (r) => r.url().includes("/api/qa") && r.request().method() === "POST",
    );
    await drawer.getByRole("button", { name: /提问/ }).click();
    await qaPromise;

    await expect(drawer.getByText("示例回答")).toBeVisible();
    await expect(drawer.getByText(/demo 模式/)).toBeVisible();
  });

  test("SourceHealth rows render the (示例) suffix in demo mode", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("数据源健康")).toBeVisible();

    // (示例) is rendered as a small orange span next to each row's detail.
    const demoMarkers = page.locator("text=(示例)");
    const count = await demoMarkers.count();
    expect(count).toBeGreaterThan(0);
  });
});
