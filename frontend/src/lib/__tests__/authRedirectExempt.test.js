/**
 * Regression tests for the API client's 401 "staff-login redirect" exemption.
 *
 * The global axios 401 interceptor hard-redirects the whole SPA to the STAFF
 * `/signin` — correct for owner/staff/admin endpoints, but wrong for the auth
 * flow itself and for *customer*-authenticated (IsCustomer) endpoints, whose
 * expiry must be surfaced by the page (re-open the customer sign-in modal).
 *
 * Guards the fix for the bug where CustomerAccount's ride-history fetch
 * (GET /rides/history/, IsCustomer) 401'd on a stale customer session and
 * bounced the customer to the staff login: `/rides/` must stay exempt.
 */
import { describe, it, expect } from "vitest";
import { isAuthRedirectExempt, AUTH_REDIRECT_EXEMPT_PATHS } from "../api";

describe("isAuthRedirectExempt", () => {
  it("exempts /rides/ so a stale customer session is not bounced to the staff /signin", () => {
    expect(isAuthRedirectExempt("/rides/history/")).toBe(true);
    expect(isAuthRedirectExempt("/rides/active/")).toBe(true);
    // full URLs (axios sometimes passes an absolute config.url) still match
    expect(isAuthRedirectExempt("https://menu.example.com/api/rides/history/")).toBe(true);
  });

  it("keeps the existing customer-auth + auth-flow endpoints exempt", () => {
    expect(isAuthRedirectExempt("/session/")).toBe(true);
    expect(isAuthRedirectExempt("/customer/profile/")).toBe(true);
    expect(isAuthRedirectExempt("/signin/")).toBe(true);
    expect(isAuthRedirectExempt("/signout/")).toBe(true);
    expect(isAuthRedirectExempt("/forgot-password/")).toBe(true);
    expect(isAuthRedirectExempt("/reset-password/")).toBe(true);
    expect(isAuthRedirectExempt("/activate/")).toBe(true);
  });

  it("still redirects genuine owner/staff/admin endpoints (not exempt)", () => {
    expect(isAuthRedirectExempt("/orders/")).toBe(false);
    expect(isAuthRedirectExempt("/admin/analytics/")).toBe(false);
    expect(isAuthRedirectExempt("/menu/items/")).toBe(false);
  });

  it("treats a null/undefined url as not-exempt (safe default)", () => {
    expect(isAuthRedirectExempt(undefined)).toBe(false);
    expect(isAuthRedirectExempt(null)).toBe(false);
    expect(isAuthRedirectExempt("")).toBe(false);
  });

  it("exports the exemption list including /rides/", () => {
    expect(AUTH_REDIRECT_EXEMPT_PATHS).toContain("/rides/");
    expect(AUTH_REDIRECT_EXEMPT_PATHS).toContain("/customer/");
  });
});
