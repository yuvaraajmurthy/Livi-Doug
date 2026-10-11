import type { Page } from "@playwright/test";

/** Save light and dark screenshots of the current page to test-results/screens/<name>-<scheme>.png. */
export async function shoot(page: Page, name: string, opts: { fullPage?: boolean } = {}) {
  for (const scheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await page.waitForTimeout(250);
    await page.screenshot({ path: `test-results/screens/${name}-${scheme}.png`, fullPage: opts.fullPage ?? true });
  }
  await page.emulateMedia({ colorScheme: "light", reducedMotion: "no-preference" });
}
