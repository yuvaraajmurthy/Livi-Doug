import { test, expect } from "@playwright/test";
import { writeFileSync } from "node:fs";
import { MAIN_STORY } from "../../src/demo/story";

// npx playwright test record --project=stage   (re-captures src/demo/replay/recording.json from production)
test("record the stage story for offline replay", async ({ page }) => {
  test.skip(test.info().project.name !== "stage" || !process.env.RECORD, "set RECORD=1 to re-record");
  test.setTimeout(420_000);
  await page.goto("/present?record=1");
  const next = page.locator("[data-stage-next]");
  await page.waitForTimeout(1500);
  for (let i = 1; i < MAIN_STORY.length; i++) {
    await page.keyboard.press("ArrowRight");
    await expect(next).toHaveText(/^Next/, { timeout: 40_000 });
    await page.waitForTimeout(400);
  }
  const frame = page.frame({ name: "compass-stage" })!;
  const calls = await frame.evaluate(() => (globalThis as { __compassRecording?: unknown[] }).__compassRecording ?? []);
  expect(calls.length).toBeGreaterThan(20);
  writeFileSync("src/demo/replay/recording.json", JSON.stringify({ recordedAt: new Date().toISOString(), calls }, null, 0));
});
