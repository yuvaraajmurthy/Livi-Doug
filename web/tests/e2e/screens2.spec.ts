import { test, expect, type Page } from "@playwright/test";
import { shoot } from "./shoot";

async function startAs(page: Page, name: RegExp) {
  await page.goto("/");
  await page.getByRole("button", { name }).click();
  await page.waitForURL(/\/(focus|next)/);
}

async function focus(page: Page, area: RegExp, barriers: RegExp[], words?: string) {
  await page.getByRole("button", { name: /Choose one area|Elige un área/ }).click();
  await page.getByRole("button", { name: area }).click();
  await page.getByRole("button", { name: /Continue|Continuar/ }).click();
  for (const b of barriers) await page.getByRole("button", { name: b }).click();
  if (words) await page.getByLabel(/In your own words|Con tus palabras/).fill(words);
  await page.getByRole("button", { name: /Find my step|Buscar mi paso/ }).click();
  await page.waitForURL(/\/next/);
  await expect(page.getByTestId("step-card")).toBeVisible({ timeout: 20_000 });
  await page.waitForTimeout(600);
}

test.describe("screens 2", () => {
  test.beforeEach(() => test.skip(test.info().project.name !== "phone", "phone only"));

  test("andre tabs", async ({ page }) => {
    await startAs(page, /Andre/);
    await focus(page, /Social/, [/No time between class/, /I don't know anyone/]);
    await page.getByRole("button", { name: /Ask about Rutgers/ }).click();
    await page.getByRole("textbox", { name: "Ask Compass" }).fill("free food this week?");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect(page.getByRole("dialog")).toContainText(/./, { timeout: 20_000 });
    await page.waitForTimeout(3500);
    await shoot(page, "20-ask", { fullPage: false });
    await page.keyboard.press("Escape");
    await page.getByRole("link", { name: "Map" }).click();
    await expect(page.getByTestId("dim-row").first()).toBeVisible();
    await page.waitForTimeout(800);
    await shoot(page, "21-map");
    await page.getByRole("link", { name: "Campus" }).click();
    await expect(page.getByText("Small wins")).toBeVisible();
    await page.waitForTimeout(800);
    await shoot(page, "22-campus");
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
    await focus(page, /Physical/, [/Coursework is eating my time/], "Calc II problem sets keep me up till 2");
    await expect(page.getByTestId("step-card")).toContainText(/Learning Center/);
    await shoot(page, "25-priya");
  });

  test("sofia in spanish", async ({ page }) => {
    await startAs(page, /Sofia/);
    await focus(page, /Financiero/, [/El dinero no alcanza/]);
    await shoot(page, "26-sofia");
  });
});
