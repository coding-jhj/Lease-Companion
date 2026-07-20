import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "real-api-mobile-320",
      use: { ...devices["Pixel 7"], viewport: { width: 320, height: 720 } },
    },
    {
      name: "real-api-mobile-360",
      use: { ...devices["Pixel 7"], viewport: { width: 360, height: 800 } },
    },
    {
      name: "real-api-desktop-1440",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
  ],
});
