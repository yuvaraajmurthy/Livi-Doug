import { test, expect, type Page } from "@playwright/test";
import { shoot } from "./shoot";

async function openTime(page: Page) {
  await page.getByRole("button", { name: /Change demo time/ }).click();
  await expect(page.getByRole("dialog", { name: "Demo time" })).toBeVisible();
}

test("Andre: step → plan → reminder → follow-up → next week", async ({ page }) => {
  test.skip(test.info().project.name !== "phone", "phone only");
  test.setTimeout(240_000);

  await page.goto("/");
  await page.getByRole("button", { name: /Andre/ }).click();
  // no questionnaire: straight to Today with his weakest area (Social) as the focus
  await page.waitForURL(/\/next/);
  await expect(page.getByTestId("step-card")).toContainText("Commuter lunch and board games", { timeout: 20_000 });

  await page.getByRole("button", { name: "I'm in" }).click();
  await page.waitForURL(/\/plan\//);
  await page.getByRole("button", { name: "Done" }).click();
  await page.waitForURL(/\/next/);

  // Tuesday 12:15: the reminder drops in
  await openTime(page);
  await page.getByRole("button", { name: /Skip to the next reminder/ }).click();
  const banner = page.locator('[data-tour="banner"]');
  await expect(banner).toContainText("starts in 15 minutes", { timeout: 20_000 });
  await page.waitForTimeout(500);
  await shoot(page, "12-reminder-banner", { fullPage: false });

  // Tuesday 3:30: the follow-up
  await openTime(page);
  await page.getByRole("button", { name: /Skip to the next reminder/ }).click();
  await expect(banner).toContainText("How was", { timeout: 20_000 });
  await banner.getByRole("button").click();
  await page.waitForURL(/\/followup\//);
  await page.getByRole("button", { name: "Yes" }).click();
  await page.getByRole("radio", { name: "4" }).click();
  await shoot(page, "13-followup");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("What Compass learned")).toBeVisible();
  await page.waitForTimeout(2200);
  await shoot(page, "14-followup-result");

  // The next week: a more open step, with the reason citing what Compass learned
  await page.getByRole("button", { name: "Today" }).first().click();
  await openTime(page);
  await page.getByRole("button", { name: /Mon Oct 19/ }).click();
  await expect(page.getByTestId("step-card")).toContainText(/basketball/i, { timeout: 20_000 });
  await page.waitForTimeout(600);
  await shoot(page, "15-next-week");
  await page.getByRole("button", { name: "Why this fits" }).click();
  await expect(page.getByRole("dialog")).toContainText("What Compass remembered");
  await page.waitForTimeout(900);
  await shoot(page, "16-next-week-why", { fullPage: false });
});
