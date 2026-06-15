/**
 * Unit test for PlainLayout — the chrome-less layout wrapping the standalone
 * (no-header/nav) routes: /signin, /forgot-password, /reset-password,
 * /activate, /unauthorized, the /admin-* pages, and the catch-all 404.
 *
 * Standalone routes used to render NO layout, so they exposed neither a
 * focusable <main id="main-content"> (the SPA route-change focus guard in
 * router/focusGuard.js, WCAG 2.4.3, had nothing to land on) nor a skip-link.
 * PlainLayout supplies both, mirroring the full layouts' pattern. This test
 * locks in:
 *   - exactly ONE focusable <main id="main-content"> landmark (single-main), and
 *   - a visually-hidden skip-link whose target resolves to that main.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

// Deterministic i18n: key passes through unchanged.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

import PlainLayout from "../PlainLayout.vue";

const mountPlain = () =>
  mount(PlainLayout, {
    global: {
      stubs: {
        // Stand-in for the routed page so we can mount without a real router.
        RouterView: { template: "<div data-test='page'>page</div>" },
      },
    },
  });

describe("PlainLayout (standalone-route a11y landmark + skip-link)", () => {
  it("renders exactly one focusable <main id='main-content'>", () => {
    const w = mountPlain();
    const mains = w.findAll("main");
    expect(mains).toHaveLength(1);

    const main = mains[0];
    expect(main.attributes("id")).toBe("main-content");
    // tabindex="-1" makes the landmark programmatically focusable so the
    // route-change focus guard can call main.focus().
    expect(main.attributes("tabindex")).toBe("-1");
  });

  it("exposes a skip-link whose target resolves to #main-content", () => {
    const w = mountPlain();
    const skip = w.find("a[href='#main-content']");
    expect(skip.exists()).toBe(true);
    // Skip-link text comes from the shared i18n key reused across all layouts.
    expect(skip.text()).toBe("common.skipToMain");

    // The anchor target must resolve to the single main landmark.
    const main = w.find("main#main-content");
    expect(main.exists()).toBe(true);
  });

  it("keeps the skip-link visually hidden until focused (sr-only)", () => {
    const w = mountPlain();
    const skip = w.find("a[href='#main-content']");
    // Same visually-hidden-until-focus pattern the full layouts use.
    expect(skip.classes()).toContain("sr-only");
    expect(skip.classes()).toContain("focus:not-sr-only");
  });

  it("renders the routed page inside the main landmark", () => {
    const w = mountPlain();
    const main = w.find("main#main-content");
    expect(main.find("[data-test='page']").exists()).toBe(true);
  });
});
