import { defineConfig } from "@playwright/test";

const frontendUrl = process.env.E2E_FRONTEND_URL || "http://demo.localhost:5173";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 180_000,
  workers: 1,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: frontendUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
});
