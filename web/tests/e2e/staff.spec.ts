import { test, expect } from "@playwright/test";
import { shoot } from "./shoot";

test("staff pulse", async ({ page }) => {
  test.skip(test.info().project.name !== "stage", "desktop only");
  await page.goto("/");
  await page.getByRole("button", { name: "Staff Pulse" }).click();
  await page.waitForURL(/\/staff/);
  await expect(page.getByText("From suggestion to")).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(600);
  await shoot(page, "30-staff-overview");
  await page.getByRole("link", { name: "Where supply is thin" }).click();
  await expect(page.getByTestId("gap-callout")).toBeVisible();
  await shoot(page, "31-staff-gaps");
  await page.getByRole("button", { name: "Try to see a small group" }).click();
  await page.waitForTimeout(2500);
  await shoot(page, "32-staff-narrow");
  await page.getByRole("button", { name: "Clear" }).click();
  await page.getByRole("link", { name: "Trends" }).click();
  await expect(page.getByRole("figure")).toBeVisible();
  await page.waitForTimeout(600);
  await shoot(page, "33-staff-trends");
  await expect(page.getByRole("link", { name: "Ask the data" })).toHaveCount(0);
});
