import { defineConfig, devices } from "@playwright/test";

const BASE = process.env.WEB_URL ?? "http://127.0.0.1:5180";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  outputDir: "test-results/artifacts",
  use: { baseURL: BASE, trace: "retain-on-failure" },
  webServer: process.env.WEB_URL
    ? undefined
    : { command: "npx vite --host 127.0.0.1 --port 5180 --strictPort", url: BASE, reuseExistingServer: true, timeout: 120_000 },
  projects: [
    { name: "phone", use: { ...devices["iPhone 13"], browserName: "chromium", viewport: { width: 390, height: 844 } } },
    { name: "stage", use: { browserName: "chromium", viewport: { width: 1280, height: 720 } } },
  ],
});
