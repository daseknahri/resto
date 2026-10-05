import { describe, it, expect, vi, afterEach } from "vitest";

const { sentryInit } = vi.hoisted(() => ({ sentryInit: vi.fn() }));

vi.mock("@sentry/vue", () => ({
  init: sentryInit,
  browserTracingIntegration: vi.fn(() => ({ name: "BrowserTracing" })),
  setTag: vi.fn(),
}));
vi.mock("../../router/index.js", () => ({ default: {} }));

const TOKEN = "3f9c0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2d3e4f5";

describe("initSentry — bearer-token scrubbing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("registers hooks that redact activation/reset tokens from events, transactions and breadcrumbs", async () => {
    vi.stubEnv("VITE_SENTRY_DSN", "https://public@sentry.example.com/1");
    const { initSentry } = await import("../sentry.js");
    initSentry({});
    await vi.waitFor(() => expect(sentryInit).toHaveBeenCalledTimes(1));

    const options = sentryInit.mock.calls[0][0];
    for (const hook of ["beforeSend", "beforeSendTransaction", "beforeBreadcrumb"]) {
      expect(typeof options[hook]).toBe("function");
    }

    const event = options.beforeSend({ request: { url: `https://demo.example.com/activate?token=${TOKEN}` } });
    expect(event.request.url).not.toContain(TOKEN);
    const transaction = options.beforeSendTransaction({ request: { url: `https://demo.example.com/reset-password?token=${TOKEN}` } });
    expect(transaction.request.url).not.toContain(TOKEN);
    const crumb = options.beforeBreadcrumb({ category: "navigation", data: { from: `/activate?token=${TOKEN}`, to: "/onboarding" } });
    expect(crumb.data.from).not.toContain(TOKEN);
    expect(crumb.data.to).toBe("/onboarding");
  });
});
