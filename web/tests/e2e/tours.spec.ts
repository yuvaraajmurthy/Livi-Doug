import { test, expect, type Page } from "@playwright/test";
import { shoot } from "./shoot";

async function runTour(page: Page, name: string, shots: number[] = []) {
  await page.goto("/tour");
  await page.getByRole("button", { name: new RegExp(name) }).first().click();
  const coach = page.locator("[data-coach]");
  await expect(coach).toBeVisible({ timeout: 20_000 });
  for (let i = 0; i < 20; i++) {
    if ((await page.getByLabel("Tour complete").count()) || !(await coach.count())) break;
    const label = (await coach.textContent({ timeout: 5000 }).catch(() => "")) ?? "";
    if (!label) continue;
    const m = label.match(/Step (\d+) of/);
    if (m && shots.includes(Number(m[1]))) await shoot(page, `40-tour-${name.toLowerCase()}-${m[1]}`, { fullPage: false });
    // a step waiting on its signal keeps the button busy; the last one ends on the completion screen instead
    const btn = page.locator("[data-coach-primary]:enabled");
    const done = page.getByLabel("Tour complete");
    await expect(btn.or(done), `stalled at: ${label}`).toBeVisible({ timeout: 25_000 });
    if (await done.count()) break;
    await btn.click();
    await page.waitForTimeout(1200);
  }
  await expect(page.getByLabel("Tour complete")).toBeVisible({ timeout: 20_000 });
  await shoot(page, `41-tour-${name.toLowerCase()}-done`, { fullPage: false });
}

test.describe("table tours on production", () => {
  test.beforeEach(() => test.skip(test.info().project.name !== "phone", "phone only"));
  test.setTimeout(240_000);
  test("andre", async ({ page }) => runTour(page, "Andre", [2, 7]));
  test("jordan", async ({ page }) => runTour(page, "Jordan", [5, 6]));
  test("priya", async ({ page }) => runTour(page, "Priya", [2]));
  test("sofia", async ({ page }) => runTour(page, "Sofia", [2]));
  test("taylor", async ({ page }) => runTour(page, "Taylor", [2]));
  test("staff", async ({ page }) => runTour(page, "Staff Pulse", [3]));
});
