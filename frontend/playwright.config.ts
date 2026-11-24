import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

const chromiumBinary = "/home/robi/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome";
const backendDir = "../backend";
const backendDatabase = "/home/robi/Desktop/freelanceflow/backend/e2e-test.db";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3011",
    trace: "retain-on-failure",
    launchOptions: existsSync(chromiumBinary)
      ? { executablePath: chromiumBinary, args: ["--no-sandbox"] }
      : { args: ["--no-sandbox"] },
    ...devices["Desktop Chrome"],
  },
  webServer: [
    {
      command: `bash -c 'rm -f ${backendDatabase}; DATABASE_URL=sqlite:///${backendDatabase} .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011'`,
      cwd: backendDir,
      url: "http://127.0.0.1:8011/api/health",
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: "npm run start -- --port 3011",
      cwd: ".",
      env: { API_BACKEND_URL: "http://127.0.0.1:8011", NODE_ENV: "production" },
      url: "http://127.0.0.1:3011",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
