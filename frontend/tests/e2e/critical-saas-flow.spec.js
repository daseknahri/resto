import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "e2e-admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "E2E_Admin_123!";

const randomSuffix = () => `${Date.now()}${Math.floor(Math.random() * 10_000)}`;

const extractActivationUrl = (text) => {
  const match = String(text || "").match(/https?:\/\/[^\s]+\/activate\?token=[a-f0-9]{40,}/i);
  return match ? match[0] : "";
};

const submitLeadWithRetry = async (page, attempts = 3) => {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const responsePromise = page.waitForResponse((response) => {
      return response.url().includes("/api/leads/") && response.request().method() === "POST";
    });
    await page.getByRole("button", { name: /submit lead/i }).click();
    const response = await responsePromise;
    if (response.status() === 201) return;
    if (response.status() !== 429 || attempt === attempts) {
      throw new Error(`Lead submission failed with status ${response.status()} on attempt ${attempt}`);
    }
    await page.waitForTimeout(2000 * attempt);
  }
};

test.describe.configure({ mode: "serial" });

test("public lead -> admin provision -> activation -> onboarding -> publish", async ({ page, baseURL }) => {
  const appBaseUrl = baseURL || "http://demo.localhost:5173";
  const suffix = randomSuffix();
  const leadName = `E2E Lead ${suffix}`;
  const leadEmail = `e2e+${suffix}@example.com`;
  const ownerPassword = `Owner_${suffix}!Aa`;
  const categoryName = `E2E Category ${suffix}`;
  const dishName = `E2E Dish ${suffix}`;

  await page.addInitScript(() => {
    window.localStorage.setItem("resto.locale", "en");
    window.localStorage.setItem("resto.locale:demo.localhost", "en");
    window.localStorage.setItem("resto.locale:localhost", "en");
  });

  await page.goto(`${appBaseUrl}/get-started`);
  await expect(page).toHaveURL(/\/get-started/);
  await page.locator('input[autocomplete="name"]').fill(leadName);
  await page.locator('input[type="email"]').fill(leadEmail);
  await page.locator('input[inputmode="tel"]').first().fill("+212600000000");
  await page.locator("textarea").first().fill("Critical SaaS flow E2E test submission.");

  await submitLeadWithRetry(page);

  await page.goto(`${appBaseUrl}/signin`);
  await expect(page).toHaveURL(/\/signin/);
  await page.locator('input[autocomplete="username"]').fill(ADMIN_EMAIL);
  await page.locator('input[autocomplete="current-password"]').fill(ADMIN_PASSWORD);

  const loginResponse = page.waitForResponse((response) => {
    return response.url().includes("/api/login/") && response.request().method() === "POST" && response.status() === 200;
  });
  await page.getByRole("button", { name: /sign in/i }).click();
  await loginResponse;
  await expect(page).toHaveURL(/\/admin-console/, { timeout: 30_000 });

  const incomingLeadsSection = page.locator("section").filter({ hasText: /incoming leads/i }).first();
  await expect(incomingLeadsSection).toBeVisible();
  await incomingLeadsSection.getByRole("button", { name: /refresh leads/i }).click();

  const leadCard = incomingLeadsSection.locator("div.rounded-xl").filter({ hasText: leadEmail }).first();
  await expect(leadCard).toBeVisible({ timeout: 30_000 });

  const provisionResponse = page.waitForResponse((response) => {
    return response.url().includes("/api/lead-provision/") && response.request().method() === "PUT" && response.status() === 200;
  });
  await leadCard.getByRole("button", { name: /^provision$/i }).click();
  await provisionResponse;

  const packageSection = page.locator("section").filter({ hasText: /latest provisioning package/i }).first();
  await expect(packageSection).toBeVisible({ timeout: 30_000 });
  const packageText = await packageSection.innerText();
  const activationUrl = extractActivationUrl(packageText);
  expect(activationUrl).toBeTruthy();

  const tenantOrigin = new URL(activationUrl).origin;

  await page.goto(activationUrl);
  await expect(page).toHaveURL(/\/activate/, { timeout: 30_000 });
  await page.locator('input[type="password"]').fill(ownerPassword);

  const activationResponse = page.waitForResponse((response) => {
    return response.url().includes("/api/activate/") && response.request().method() === "POST" && response.status() === 200;
  });
  await page.getByRole("button", { name: /activate/i }).click();
  await activationResponse;
  await expect(page).toHaveURL(/\/owner\/onboarding/, { timeout: 30_000 });

  await page.getByLabel("Tagline").fill(`E2E Tagline ${suffix}`);
  await page.getByLabel("Phone").fill("+212611111111");
  await page.getByRole("button", { name: /save & next/i }).click();
  await expect(page.getByRole("heading", { name: /^categories$/i })).toBeVisible({ timeout: 20_000 });

  await page.getByPlaceholder("Category name").first().fill(categoryName);
  await page.getByRole("button", { name: /save & next/i }).click();
  await expect(page.getByRole("heading", { name: /^dishes$/i })).toBeVisible({ timeout: 20_000 });

  await page.getByPlaceholder("Dish name").first().fill(dishName);
  await page.locator("select").first().selectOption({ index: 1 });
  await page.getByPlaceholder("Price").first().fill("10");
  await page.getByRole("button", { name: /save & next/i }).click();
  await expect(page.getByRole("heading", { name: /^theme$/i })).toBeVisible({ timeout: 20_000 });

  await page.getByRole("button", { name: /save & next/i }).click();
  await expect(page.getByRole("heading", { name: /^publish$/i })).toBeVisible({ timeout: 20_000 });

  const publishResponse = page.waitForResponse((response) => {
    return response.url().includes("/api/profile/") && response.request().method() === "PUT" && response.status() === 200;
  });
  await page.getByRole("button", { name: /publish menu/i }).click();
  await publishResponse;
  await expect(page).toHaveURL(/\/owner\/launch/, { timeout: 30_000 });

  await page.goto(`${tenantOrigin}/browse`);
  await expect(page).toHaveURL(/\/browse/);
  await expect(page.locator("body")).toContainText(categoryName);
});
