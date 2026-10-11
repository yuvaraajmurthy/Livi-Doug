import { test, expect } from "@playwright/test";
import { shoot } from "./shoot";

test("chat: ask → event buttons → card with map → remind me", async ({ page }) => {
  test.skip(test.info().project.name !== "phone", "phone only");
  test.setTimeout(180_000);
  await page.goto("/");
  await page.getByRole("button", { name: /Andre/ }).click();
  await page.waitForURL(/\/next/);
  await page.goto("/chat");
  await expect(page.getByText(/Hi Andre/)).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(500);
  await shoot(page, "70-chat-empty", { fullPage: false });
  await page.locator('[data-tour="chat-chip-0"]').click();
  const firstEvent = page.locator('[data-tour="chat-event-0"]');
  await expect(firstEvent).toBeVisible({ timeout: 45_000 });
  await expect(page.locator('[data-tour="chat-send"]')).toBeDisabled();
  await page.waitForTimeout(3000);
  await shoot(page, "71-chat-answer", { fullPage: false });
  await firstEvent.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("button", { name: "Remind me" })).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(3500);
  await shoot(page, "72-event-card", { fullPage: false });
  await dialog.getByRole("button", { name: "Remind me" }).click();
  await expect(dialog.getByText(/Reminder set/)).toBeVisible({ timeout: 20_000 });
  await shoot(page, "73-event-reminded", { fullPage: false });
});
