import { expect, test } from "@playwright/test";

const TENANT_FRONTEND = process.env.E2E_FRONTEND_URL || "http://demo.localhost:5173";
const PUBLIC_FRONTEND = process.env.E2E_PUBLIC_FRONTEND_URL || "http://localhost:5173";

const OWNER_EMAIL = process.env.E2E_OWNER_EMAIL || "test_resto_user@demo.local";
const OWNER_PASSWORD = process.env.E2E_OWNER_PASSWORD || "admin123";

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "e2e-admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || "E2E_Admin_123!";

test.use({ viewport: { width: 390, height: 844 } });
test.describe.configure({ mode: "serial" });

const setLocale = async (page) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("resto.locale", "en");
    window.localStorage.setItem("resto.locale:demo.localhost", "en");
    window.localStorage.setItem("resto.locale:localhost", "en");
  });
};

const assertNoHorizontalOverflow = async (page, label) => {
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(300);
  const dimensions = await page.evaluate(() => {
    const root = document.documentElement;
    const body = document.body;
    const clientWidth = root.clientWidth;
    // On overflow, identify the TRUE culprits: the deepest elements whose right edge
    // crosses the viewport AND are NOT clipped by a scroll/hidden ancestor. An element
    // inside e.g. an overflow-x-auto rail extends past the viewport in layout but is
    // clipped, so it does NOT push the body wide — only uncontained ones do. Reported
    // in the assertion message so a failure names the real offending nodes.
    const isClipped = (el) => {
      for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
        const ox = getComputedStyle(a).overflowX;
        if ((ox === "hidden" || ox === "auto" || ox === "scroll") &&
            a.getBoundingClientRect().right <= clientWidth + 2) return true;
      }
      return false;
    };
    const offenders = [];
    const max = Math.max(root.scrollWidth, body ? body.scrollWidth : root.scrollWidth);
    if (max > clientWidth + 2) {
      for (const el of document.querySelectorAll("body *")) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.right <= clientWidth + 2) continue;
        if (isClipped(el)) continue; // clipped by an ancestor — not a real cause
        const childOverflows = Array.from(el.children).some((c) => {
          const cr = c.getBoundingClientRect();
          return cr.width > 0 && cr.right > clientWidth + 2 && !isClipped(c);
        });
        if (childOverflows) continue; // a parent stretched by a real child — skip
        // Ancestor chain (tag.class up to body) to locate the owning component.
        const path = [];
        for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
          const c = String(a.className || "").trim().split(/\s+/).slice(0, 2).join(".");
          path.unshift(a.tagName.toLowerCase() + (c ? "." + c : ""));
          if (path.length >= 6) break;
        }
        offenders.push({
          tag: el.tagName.toLowerCase(),
          cls: String(el.className || "").slice(0, 140),
          right: Math.round(r.right),
          width: Math.round(r.width),
          text: (el.textContent || "").trim().slice(0, 40),
          html: el.outerHTML.slice(0, 240),
          path: path.join(" > "),
        });
      }
      offenders.sort((a, b) => b.right - a.right);
    }
    return {
      clientWidth,
      rootScrollWidth: root.scrollWidth,
      bodyScrollWidth: body ? body.scrollWidth : root.scrollWidth,
      offenders: offenders.slice(0, 8),
    };
  });
  expect(
    Math.max(dimensions.rootScrollWidth, dimensions.bodyScrollWidth),
    `${label} should not overflow horizontally on mobile viewport (clientWidth=${dimensions.clientWidth}). ` +
      `Overflowing (uncontained) elements: ${JSON.stringify(dimensions.offenders, null, 2)}`
  ).toBeLessThanOrEqual(dimensions.clientWidth + 2);
};

const signIn = async (page, appBaseUrl, email, password) => {
  await page.goto(`${appBaseUrl}/signin`);
  await expect(page).toHaveURL(/\/signin/);
  await page.locator('input[autocomplete="username"]').fill(email);
  await page.locator('input[autocomplete="current-password"]').fill(password);
  const loginResponse = page.waitForResponse((response) => {
    return response.url().includes("/api/login/") && response.request().method() === "POST";
  });
  await page.getByRole("button", { name: /sign in/i }).click();
  const response = await loginResponse;
  expect(response.status(), `login should succeed for ${email}`).toBe(200);
};

test("mobile landing and customer pages remain usable without horizontal overflow", async ({ page }) => {
  await setLocale(page);

  await page.goto(`${PUBLIC_FRONTEND}/get-started`);
  await expect(page).toHaveURL(/\/get-started/);
  await expect(page.locator('input[autocomplete="name"]')).toBeVisible();
  await assertNoHorizontalOverflow(page, "Landing lead capture");

  await page.goto(`${TENANT_FRONTEND}/menu`);
  await expect(page).toHaveURL(/\/menu/);
  await assertNoHorizontalOverflow(page, "Customer info page");

  await page.goto(`${TENANT_FRONTEND}/browse`);
  await expect(page).toHaveURL(/\/browse/);
  await assertNoHorizontalOverflow(page, "Customer browse page");

  await page.goto(`${TENANT_FRONTEND}/cart`);
  await expect(page).toHaveURL(/\/cart/);
  await assertNoHorizontalOverflow(page, "Customer cart page");

  await page.goto(`${TENANT_FRONTEND}/reserve`);
  await expect(page).toHaveURL(/\/reserve/);
  await assertNoHorizontalOverflow(page, "Customer reservation page");
});

test("mobile owner workspace stays readable across core routes", async ({ page }) => {
  await setLocale(page);
  await signIn(page, TENANT_FRONTEND, OWNER_EMAIL, OWNER_PASSWORD);
  await expect(page).toHaveURL(/\/owner(\/|$)/, { timeout: 30_000 });

  await page.goto(`${TENANT_FRONTEND}/owner`);
  await expect(page).toHaveURL(/\/owner(\/|$)/);
  await assertNoHorizontalOverflow(page, "Owner home");

  await page.goto(`${TENANT_FRONTEND}/owner/onboarding`);
  await expect(page).toHaveURL(/\/owner\/onboarding/);
  await assertNoHorizontalOverflow(page, "Owner onboarding");

  await page.goto(`${TENANT_FRONTEND}/owner/tables`);
  await expect(page).toHaveURL(/\/owner\/tables/);
  await assertNoHorizontalOverflow(page, "Owner tables");

  await page.goto(`${TENANT_FRONTEND}/owner/reservations`);
  await expect(page).toHaveURL(/\/owner\/reservations/);
  await assertNoHorizontalOverflow(page, "Owner reservations");
});

test("mobile admin console uses card-safe layout without horizontal overflow", async ({ page }) => {
  await setLocale(page);
  await signIn(page, TENANT_FRONTEND, ADMIN_EMAIL, ADMIN_PASSWORD);
  await expect(page).toHaveURL(/\/admin-console/, { timeout: 30_000 });
  await assertNoHorizontalOverflow(page, "Admin console");
});
