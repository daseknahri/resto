import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "e2e-admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "E2E_Admin_123!";
const TENANT_FRONTEND = process.env.E2E_FRONTEND_URL || "http://demo.localhost:5173";
const PUBLIC_FRONTEND = process.env.E2E_PUBLIC_FRONTEND_URL || "http://127.0.0.1:5173";
const TENANT_API = process.env.E2E_API_URL || "http://demo.localhost:8000";

test.describe.configure({ mode: "serial" });

test("cross-host session scope and CSRF protection", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("resto.locale", "en");
    window.localStorage.setItem("resto.locale:demo.localhost", "en");
    window.localStorage.setItem("resto.locale:localhost", "en");
  });

  await page.goto(`${TENANT_FRONTEND}/signin`);
  await expect(page).toHaveURL(/\/signin/);
  await page.locator('input[autocomplete="username"]').fill(ADMIN_EMAIL);
  await page.locator('input[autocomplete="current-password"]').fill(ADMIN_PASSWORD);

  const loginResponse = page.waitForResponse((response) => {
    return response.url().includes("/api/login/") && response.request().method() === "POST" && response.status() === 200;
  });
  await page.getByRole("button", { name: /sign in/i }).click();
  await loginResponse;
  await expect(page).toHaveURL(/\/admin-console/, { timeout: 30_000 });
  await expect(page.locator("body")).toContainText(/provisioning and operations/i);

  await page.goto(`${PUBLIC_FRONTEND}/admin-console`);
  await expect(page).toHaveURL(/\/signin/, { timeout: 30_000 });
  await expect(page.locator("body")).toContainText(/sign in/i);

  await page.goto(`${TENANT_FRONTEND}/admin-console`);
  await expect(page).toHaveURL(/\/admin-console/, { timeout: 30_000 });

  const noCsrfStatus = await page.evaluate(async (apiBase) => {
    const response = await fetch(`${apiBase}/api/logout/`, {
      method: "POST",
      credentials: "include",
    });
    return response.status;
  }, TENANT_API);
  expect(noCsrfStatus).toBe(403);

  const withCsrfStatus = await page.evaluate(async (apiBase) => {
    const csrfMatch = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    const csrfToken = csrfMatch ? decodeURIComponent(csrfMatch[1]) : "";
    const response = await fetch(`${apiBase}/api/logout/`, {
      method: "POST",
      credentials: "include",
      headers: {
        "X-CSRFToken": csrfToken,
      },
    });
    return response.status;
  }, TENANT_API);
  expect(withCsrfStatus).toBe(200);

  const sessionState = await page.evaluate(async (apiBase) => {
    const response = await fetch(`${apiBase}/api/session/`, {
      method: "GET",
      credentials: "include",
    });
    if (!response.ok) return { status: response.status, authenticated: null };
    const payload = await response.json();
    return { status: response.status, authenticated: payload?.authenticated };
  }, TENANT_API);
  expect([200, 403]).toContain(sessionState?.status);
  if (sessionState?.status === 200) {
    expect(sessionState?.authenticated).toBe(false);
  }
});
