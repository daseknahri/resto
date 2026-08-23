import { describe, it, expect } from "vitest";
import { sanitizeNext } from "../SignIn.vue";

// SECURITY regression: the `next` query param feeds both an in-app router.push
// and a cross-host full-URL redirect (window.location.assign) on the owner
// post-login path. Before this guard, an attacker-crafted `next` could steer the
// just-authenticated owner to an external origin (open redirect → phishing /
// token leak). sanitizeNext must pass legitimate first-party relative paths
// unchanged and collapse everything else to the safe default (/owner).
describe("SignIn sanitizeNext (open-redirect guard)", () => {
  it("passes a normal internal path unchanged", () => {
    expect(sanitizeNext("/owner")).toBe("/owner");
    expect(sanitizeNext("/owner/orders")).toBe("/owner/orders");
    // A first-party path may carry a query string / nested slashes.
    expect(sanitizeNext("/owner/menu?tab=live")).toBe("/owner/menu?tab=live");
  });

  it("rejects a scheme-relative '//host' path (external origin)", () => {
    expect(sanitizeNext("//evil.com")).toBe("/owner");
  });

  it("rejects an absolute external URL", () => {
    expect(sanitizeNext("https://evil.com")).toBe("/owner");
    expect(sanitizeNext("http://evil.com/steal")).toBe("/owner");
  });

  it("rejects a backslash-authority '/\\host' path (browsers normalize \\ to /)", () => {
    expect(sanitizeNext("/\\evil.com")).toBe("/owner");
  });

  it("rejects any value containing '@' (userinfo in an authority)", () => {
    expect(sanitizeNext("/foo@evil.com")).toBe("/owner");
    expect(sanitizeNext("https://user@evil.com")).toBe("/owner");
  });

  it("falls back to the safe default for empty / non-string / relative-without-leading-slash input", () => {
    expect(sanitizeNext("")).toBe("/owner");
    expect(sanitizeNext(undefined)).toBe("/owner");
    expect(sanitizeNext(null)).toBe("/owner");
    expect(sanitizeNext("owner")).toBe("/owner");
    expect(sanitizeNext("javascript:alert(1)")).toBe("/owner");
  });
});
