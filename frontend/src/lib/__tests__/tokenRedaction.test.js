import { describe, it, expect, vi } from "vitest";
import { REDACTED, redactTokensInUrl, scrubSentryPayload, stripTokenFromUrl } from "../tokenRedaction";

const TOKEN = "3f9c0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5";

describe("redactTokensInUrl", () => {
  it("redacts the token query param and keeps the rest of the URL", () => {
    expect(redactTokensInUrl(`https://demo.example.com/activate?token=${TOKEN}&next=%2Fowner`)).toBe(
      `https://demo.example.com/activate?token=${REDACTED}&next=%2Fowner`,
    );
    expect(redactTokensInUrl(`/reset-password?next=/x&token=${TOKEN}#top`)).toBe(
      `/reset-password?next=/x&token=${REDACTED}#top`,
    );
  });

  it("redacts URL-encoded and path-segment tokens", () => {
    expect(redactTokensInUrl(`https://wa.me/1?text=activate%3Ftoken%3D${TOKEN}%0A`)).not.toContain(TOKEN);
    expect(redactTokensInUrl(`https://x.test/activate/${TOKEN}`)).toBe(`https://x.test/activate/${REDACTED}`);
    expect(redactTokensInUrl(`https://x.test/r/${TOKEN}?a=1`)).toBe(`https://x.test/r/${REDACTED}?a=1`);
  });

  it("leaves token-free strings and non-strings untouched", () => {
    expect(redactTokensInUrl("https://demo.example.com/menu?lang=fr")).toBe("https://demo.example.com/menu?lang=fr");
    expect(redactTokensInUrl(undefined)).toBeUndefined();
    expect(redactTokensInUrl(42)).toBe(42);
  });
});

describe("scrubSentryPayload", () => {
  it("redacts request.url, Referer, transaction and breadcrumbs of an event in place", () => {
    const scope = new (class Scope {
      constructor() {
        this.note = `token=${TOKEN}`;
      }
    })();
    const event = {
      transaction: `/activate?token=${TOKEN}`,
      request: { url: `https://demo.example.com/activate?token=${TOKEN}`, headers: { Referer: `https://demo.example.com/reset-password?token=${TOKEN}` } },
      breadcrumbs: [
        { category: "navigation", data: { from: `/activate?token=${TOKEN}`, to: "/activate" } },
        { category: "xhr", data: { method: "GET", url: `/api/x?token=${TOKEN}`, status_code: 200 } },
      ],
      exception: { values: [{ value: `failed at /activate?token=${TOKEN}` }] },
      sdkProcessingMetadata: { capturedSpanScope: scope },
    };
    const result = scrubSentryPayload(event);
    expect(result).toBe(event);
    const { sdkProcessingMetadata, ...userFacing } = result;
    expect(JSON.stringify(userFacing)).not.toContain(TOKEN);
    expect(result.breadcrumbs[0].data.to).toBe("/activate");
    expect(result.breadcrumbs[1].data.status_code).toBe(200);
    // SDK internals (class instances) are never rewritten.
    expect(sdkProcessingMetadata.capturedSpanScope).toBe(scope);
    expect(scope.note).toContain(TOKEN);
  });

  it("works as a beforeBreadcrumb hook", () => {
    const crumb = { category: "navigation", data: { from: `/reset-password?token=${TOKEN}`, to: "/signin" } };
    expect(scrubSentryPayload(crumb).data.from).toBe(`/reset-password?token=${REDACTED}`);
  });
});

describe("stripTokenFromUrl", () => {
  it("replaces the route without the token, keeping other params", () => {
    const router = { replace: vi.fn(() => Promise.resolve()) };
    const route = { path: "/activate", hash: "", query: { token: TOKEN, next: "/owner" } };
    stripTokenFromUrl(route, router);
    expect(router.replace).toHaveBeenCalledWith({ path: "/activate", query: { next: "/owner" }, hash: "" });
    expect(route.query.token).toBe(TOKEN); // the route object itself is not mutated
  });

  it("is a no-op when the URL carries no token", () => {
    const router = { replace: vi.fn() };
    stripTokenFromUrl({ path: "/activate", query: { next: "/owner" } }, router);
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("swallows navigation failures", async () => {
    const router = { replace: vi.fn(() => Promise.reject(new Error("aborted"))) };
    expect(() => stripTokenFromUrl({ path: "/activate", query: { token: TOKEN } }, router)).not.toThrow();
    await Promise.resolve();
  });
});
