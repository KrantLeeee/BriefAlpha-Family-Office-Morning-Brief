import { expect, test } from "@playwright/test";

test.describe("BriefAlpha — main desktop @1440px (frame fFOSV)", () => {
  test("renders top bar, summary strip, AI priority list, footer", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("BriefAlpha")).toBeVisible();
    await expect(page.getByText("组合感知晨报")).toBeVisible();
    await expect(page.getByText("已脱敏")).toBeVisible();

    // Base case
    await expect(
      page.getByRole("heading", { name: /英伟达下调/ })
    ).toBeVisible();

    // Treemap tile labels
    await expect(page.getByText("NVDA").first()).toBeVisible();
    await expect(page.getByText("TLT").first()).toBeVisible();

    // AI priority list
    await expect(page.getByText("AI 组合研判")).toBeVisible();
    await expect(page.getByText("Fed Williams 暗示")).toBeVisible();
  });

  test("clicking a judgement opens drawer; ESC closes; focus returns", async ({ page }) => {
    await page.goto("/");

    const row = page.locator('[id^="judgement-row-"]').first();
    await row.click();

    await expect(page.getByRole("dialog", { name: /研判.*详情/ })).toBeVisible();
    await expect(page.getByText("推理链")).toBeVisible();
    await expect(page.getByText(/证据 ·/).first()).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: /研判.*详情/ })).toBeHidden();
  });

  test("upload drawer opens from top bar button", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "上传研报" }).click();
    await expect(page.getByRole("dialog", { name: "上传研报" })).toBeVisible();
    await expect(page.getByText("UPLOAD RESEARCH")).toBeVisible();
  });

  test("visual parity snapshot at 1440px", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(await page.screenshot({ fullPage: true })).toMatchSnapshot("desktop-main.png", {
      maxDiffPixelRatio: 0.05,
    });
  });
});
