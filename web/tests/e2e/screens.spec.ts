import { test, expect } from "@playwright/test";
import { shoot } from "./shoot";

test.describe("screens", () => {
  test.beforeEach(() => test.skip(test.info().project.name !== "phone", "phone screenshots only"));

  test("entry", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("One next step");
    await shoot(page, "01-entry");
  });

  test("andre straight to next step", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Andre/ }).click();
    await page.waitForURL(/\/next/);
    await expect(page.getByTestId("step-card")).toBeVisible({ timeout: 20_000 });
    await page.waitForTimeout(600);
    await shoot(page, "07-today");
    await page.getByRole("button", { name: "Why this fits" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.waitForTimeout(900);
    await shoot(page, "08-why", { fullPage: false });
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "I'm in" }).click();
    await page.waitForURL(/\/plan\//);
    await expect(page.getByText(/We'll remind you at/)).toBeVisible();
    await page.waitForTimeout(700);
    await shoot(page, "10-plan");
    await page.getByRole("button", { name: "Done" }).click();
    await page.waitForURL(/\/next/);
    await page.waitForTimeout(500);
    await shoot(page, "11-today-planned", { fullPage: false });
  });

  test("taylor care-first", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Taylor/ }).click();
    await page.waitForURL(/\/next/);
    await expect(page.getByTestId("support-card")).toBeVisible();
    await shoot(page, "09-taylor");
  });
});
