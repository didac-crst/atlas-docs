import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const PORT = 4173;
const BASE = `http://127.0.0.1:${PORT}`;
const python = existsSync(".venv/bin/python") ? ".venv/bin/python" : "python3";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: `${BASE}/ui/`,
    trace: "on-first-retry",
  },
  webServer: {
    command: `env ATLASDOCS_ENV=development SESSION_SECRET=e2e-session-secret SESSION_SECURE=false PYTHONPATH=src:. ${python} -m uvicorn tests.e2e_app:app --host 127.0.0.1 --port ${PORT}`,
    url: `${BASE}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"] },
    },
  ],
});
