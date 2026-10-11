import { test, expect, type Page } from "@playwright/test";
import { shoot } from "./shoot";

// No questionnaire: picking a student lands on Today with their weakest area as the focus.
async function startAs(page: Page, name: RegExp) {
  await page.goto("/");
  await page.getByRole("button", { name }).click();
  await page.waitForURL(/\/next/);
  await expect(page.getByTestId("step-card")).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(600);
}

test.describe("screens 2", () => {
  test.beforeEach(() => test.skip(test.info().project.name !== "phone", "phone only"));

  test("andre tabs", async ({ page }) => {
    await startAs(page, /Andre/);
    await page.getByRole("link", { name: "Chat" }).click();
    await page.locator('[data-tour="chat-input"]').fill("free food this week?");
    await page.locator('[data-tour="chat-send"]').click();
    await expect(page.locator('[data-tour="chat-event-0"]')).toBeVisible({ timeout: 25_000 });
    await page.waitForTimeout(1500);
    await shoot(page, "20-chat", { fullPage: false });
    await page.locator('[data-tour="chat-event-0"]').click();
    await expect(page.locator('[data-tour="event-remind"]')).toBeVisible();
    await page.waitForTimeout(1200);
    await shoot(page, "22-event", { fullPage: false });
    await page.keyboard.press("Escape");
    await page.getByRole("link", { name: "Wellness", exact: true }).click();
    await page.waitForURL(/\/wellness/);
    await expect(page.getByTestId("dim-row").first()).toBeVisible();
    await page.waitForTimeout(800);
    await shoot(page, "21-wellness");
    await page.getByRole("link", { name: "You" }).click();
    await expect(page.getByText("What Compass knows")).toBeVisible();
    await page.waitForTimeout(500);
    await shoot(page, "23-you");
    await page.getByRole("link", { name: /inside MyRutgers/ }).click();
    await expect(page.locator('[data-tour="myrutgers-card"]')).toBeVisible();
    await page.waitForTimeout(500);
    await shoot(page, "24-card");
  });

  test("priya root cause", async ({ page }) => {
    await startAs(page, /Priya/);
    await expect(page.getByTestId("step-card")).toContainText(/Learning Center/);
    await shoot(page, "25-priya");
  });

  test("sofia in spanish", async ({ page }) => {
    await startAs(page, /Sofia/);
    await expect(page.getByRole("link", { name: "Bienestar", exact: true })).toBeVisible();
    await shoot(page, "26-sofia");
  });
});
