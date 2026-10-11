import { test, expect } from "@playwright/test";

// Diagnostic: does the event-card map actually render (WebGL + OpenFreeMap tiles) in this browser?
test("event card map renders", async ({ page }) => {
  test.skip(test.info().project.name !== "phone", "phone only");
  test.setTimeout(150_000);
  const errors: string[] = [];
  const tiles: string[] = [];
  page.on("request", r => r.url().includes("openfreemap") && tiles.push(r.url().slice(0, 80)));
  page.on("requestfailed", r => r.url().includes("openfreemap") && errors.push("FAILED " + r.url().slice(0, 80) + " " + r.failure()?.errorText));
  page.on("console", m => m.type() === "error" && errors.push(m.text()));
  await page.goto("/");
  await page.getByRole("button", { name: /Andre/ }).click();
  await page.waitForURL(/\/(focus|next)/);
  await page.goto("/chat");
  await page.locator('[data-tour="chat-chip-0"]').click();
  await page.locator('[data-tour="chat-event-0"]').click({ timeout: 45_000 });
  await page.waitForTimeout(9000);
  await page.screenshot({ path: "test-results/screens/74-map-late.png" });
  const info = await page.evaluate(() => ({
    webgl: !!document.createElement("canvas").getContext("webgl"),
    canvas: !!document.querySelector(".maplibregl-canvas"),
    size: (() => { const c = document.querySelector<HTMLCanvasElement>(".maplibregl-canvas"); return c ? [c.width, c.height, c.clientWidth, c.clientHeight] : null; })(),
  }));
  console.log("MAPCHECK", JSON.stringify(info), "tiles:", tiles.length, tiles.slice(0, 3).join(" "), "errors:", errors.slice(0, 4).join(" | ").slice(0, 500));
  await expect(page.getByRole("dialog")).toBeVisible();
});
