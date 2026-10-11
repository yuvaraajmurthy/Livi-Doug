import { test, expect } from "@playwright/test";
import { MAIN_STORY } from "../../src/demo/story";

test("stage: the whole main story runs with the keyboard alone", async ({ page }) => {
  test.skip(test.info().project.name !== "stage", "stage only");
  test.setTimeout(420_000);
  await page.goto("/present");
  const next = page.locator("[data-stage-next]");
  await expect(page.getByText("Then what?")).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/screens/50-stage-00.png" });
  for (let i = 1; i < MAIN_STORY.length; i++) {
    await page.keyboard.press("ArrowRight");
    await expect(next, `step ${i} (${MAIN_STORY[i].id}) settles`).toHaveText(/^Next/, { timeout: 40_000 });
    await expect(page.locator("main, body").getByText(MAIN_STORY[i].claim, { exact: false }).first()).toBeVisible();
    await page.waitForTimeout(1600);
    await page.screenshot({ path: `test-results/screens/50-stage-${String(i).padStart(2, "0")}.png` });
  }
  const phone = page.frameLocator('iframe[name="compass-stage"]');
  await expect(page.getByText("Ready for a spring pilot at Newark.")).toBeVisible();
  void phone;
});
