import { test, expect, chromium } from "@playwright/test";
import { shoot } from "./shoot";

// Voice mode in a real browser with Chromium's fake microphone: connects over the production WebSocket and listens.
test("voice: opens, connects, listens, ends", async ({ baseURL }) => {
  test.skip(test.info().project.name !== "phone", "phone only");
  const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required"] });
  const ctx = await browser.newContext({ baseURL, viewport: { width: 390, height: 844 }, permissions: ["microphone"] });
  const page = await ctx.newPage();
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: /Andre/ }).click();
  await page.waitForURL(/\/(focus|next)/);
  await page.goto("/chat");
  await page.locator('[data-tour="voice-open"]').click();
  const status = page.locator('[data-tour="voice-overlay"] [role="status"]');
  await expect(status).toHaveText(/Listening/, { timeout: 20_000 });
  await page.waitForTimeout(1500);
  await shoot(page, "30-voice", { fullPage: false });
  await page.locator('[data-tour="voice-end"]').click();
  await expect(page.locator('[data-tour="voice-overlay"]')).toHaveCount(0);
  expect(errors).toEqual([]);
  await browser.close();
});
