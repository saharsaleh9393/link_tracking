import { defineConfig, devices } from "@playwright/test";
const port = 3100;
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
      // Only special-use loopback names bypass the environment's outbound proxy.
      args: [
        "--host-resolver-rules=MAP *.localhost 127.0.0.1",
        "--proxy-bypass-list=localhost;*.localhost;127.0.0.1;[::1]",
        ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? ["--no-sandbox"] : []),
      ],
    },
  },
  webServer: {
    command: `npm run start -- --port ${port}`,
    url: `http://127.0.0.1:${port}/login`,
    reuseExistingServer: false,
    timeout: 60000,
    env: {
      NEXT_TELEMETRY_DISABLED: "1",
      TRACKER_API_URL:
        process.env.E2E_TRACKER_API_URL || "http://127.0.0.1:8003",
      PUBLIC_BASE_URL:
        process.env.E2E_TRACKER_API_URL || "http://127.0.0.1:8003",
      ADMIN_API_KEY: "e2e-admin-" + "a".repeat(40),
      REPORT_API_KEY: "e2e-report-" + "b".repeat(40),
      DASHBOARD_PASSWORD: "e2e-workspace-password-strong-and-local",
      DASHBOARD_SESSION_SECRET: "e2e-session-secret-".repeat(4),
      DASHBOARD_SECURE_COOKIES: "false",
    },
  },
});
