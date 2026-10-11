import { test, expect } from "@playwright/test";
import { MAIN_STORY } from "../../src/demo/story";

test("offline: the stage story finishes on replay after the API is cut off", async ({ page, context }) => {
  test.skip(test.info().project.name !== "stage", "stage only");
  test.setTimeout(420_000);
  await page.goto("/present");
  const next = page.locator("[data-stage-next]");
  await page.waitForTimeout(1200);
  const cutAt = MAIN_STORY.findIndex(s => s.id === "andre-commit");
  for (let i = 1; i < MAIN_STORY.length; i++) {
    if (i === cutAt) {
      // the venue Wi-Fi dies: every API call now fails
      await context.route(/cloudfront\.net\/(me|demo|ask|commitments|followups|pulse|staff|meta|push|invites|wins)/, r => r.abort());
      await page.keyboard.press("o");
      await expect(page.getByText("Offline replay")).toBeVisible({ timeout: 10_000 });
    }
    await page.keyboard.press("ArrowRight");
    await expect(next, `step ${i} (${MAIN_STORY[i].id})`).toHaveText(/^Next/, { timeout: 40_000 });
    await expect(page.getByText(MAIN_STORY[i].claim, { exact: false }).first()).toBeVisible();
    if (i > cutAt) await page.screenshot({ path: `test-results/screens/60-offline-${String(i).padStart(2, "0")}.png` });
  }
  await expect(page.getByText("Ready for a spring pilot at Newark.")).toBeVisible();
});
