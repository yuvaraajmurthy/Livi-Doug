import { test, expect } from "@playwright/test";
import { shoot } from "./shoot";

test.describe("screens", () => {
  test.beforeEach(() => test.skip(test.info().project.name !== "phone", "phone screenshots only"));

  test("entry and shell", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("One next step");
    await shoot(page, "01-entry");
    await page.getByRole("button", { name: /Andre/ }).click();
    await page.waitForURL(/\/(focus|next)/);
    await page.goto("/next");
    await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
    await shoot(page, "02-shell", { fullPage: false });
  });
});
