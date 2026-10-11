import { test, expect } from "@playwright/test";
import { shoot } from "./shoot";

test.describe("screens", () => {
  test.beforeEach(() => test.skip(test.info().project.name !== "phone", "phone screenshots only"));

  test("entry", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("One next step");
    await shoot(page, "01-entry");
  });

  test("andre focus to next step", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Andre/ }).click();
    await page.waitForURL(/\/focus/);
    await expect(page.getByText("Here's what's going well.")).toBeVisible();
    await page.waitForTimeout(900);
    await shoot(page, "03-strengths");
    await page.getByRole("button", { name: "Choose one area to work on" }).click();
    await page.getByRole("button", { name: /Social/ }).click();
    await shoot(page, "04-pick");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByRole("button", { name: /No time between class/ }).click();
    await page.getByRole("button", { name: /I don't know anyone/ }).click();
    await shoot(page, "05-barriers");
    await page.getByRole("button", { name: "Find my step" }).click();
    await expect(page.getByText("Finding one step that fits your week")).toBeVisible();
    await page.waitForTimeout(700);
    await page.screenshot({ path: "test-results/screens/06-finding-light.png" });
    await page.waitForURL(/\/next/);
    await expect(page.getByTestId("step-card")).toBeVisible();
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
    await page.waitForURL(/\/(next|focus)/);
    if (page.url().includes("/focus")) await page.goto("/next");
    await expect(page.getByTestId("support-card")).toBeVisible();
    await shoot(page, "09-taylor");
  });
});
