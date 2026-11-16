// Chromium-only Playwright config for the #684 browser JS gate.
//
// No `webServer`: tests/browser/operator-pages.spec.mjs starts and stops the
// fixture server itself, so the suite runs standalone (`npm run test:browser`).
import { defineConfig, devices } from "@playwright/test";
import { join } from "node:path";
import { tmpdir } from "node:os";

export default defineConfig({
  testDir: "./tests/browser",
  testMatch: "**/*.spec.mjs",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  timeout: 20_000,
  globalTimeout: 120_000,
  expect: { timeout: 5_000 },
  reporter: "list",
  // Artifacts stay out of the repository tree.
  outputDir: join(tmpdir(), "sea-speed-playwright-684"),
  use: {
    baseURL: "http://127.0.0.1:8131",
    browserName: "chromium",
    headless: true,
    actionTimeout: 5_000,
    navigationTimeout: 10_000,
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
