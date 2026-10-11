import { test, expect } from "@playwright/test";
import { MAIN_STORY } from "../../src/demo/story";

test("stage: the whole main story runs with the keyboard alone", async ({ page }) => {
  test.skip(test.info().project.name !== "stage", "stage only");
  test.setTimeout(480_000);
  await page.goto("/present");
  await expect(page.getByText("Then what?")).toBeVisible();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/screens/50-stage-00.png" });
  const status = page.locator("[data-stage-status]");
  for (let i = 1; i < MAIN_STORY.length; i++) {
    await page.keyboard.press("ArrowRight");
    await expect(status, `step ${i} (${MAIN_STORY[i].id}) settles`).toHaveAttribute("data-stage-status", /^(done|idle)$/, { timeout: 60_000 });
    if (!MAIN_STORY[i].slide) await expect(page.getByRole("heading", { level: 1, name: MAIN_STORY[i].claim })).toBeVisible();
    await page.waitForTimeout(1400);
    await page.screenshot({ path: `test-results/screens/50-stage-${String(i).padStart(2, "0")}.png` });
  }
  await expect(page.getByText("Ready for a spring pilot.")).toBeVisible();
});
