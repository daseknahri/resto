/**
 * Mount smoke test for DemoLanding.vue (the demo/marketing landing page, ~119 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, bad import, unguarded
 * browser API) was never caught by a test". Mounting the page runs its real
 * setup() + first render — so any such crash fails CI here instead of in prod.
 *
 * This is a genuinely STATIC marketing page: no props, no store, no route/query,
 * no api call, no fetch, and no conditional branches. Its setup() only reads two
 * pure brand constants and the i18n `t`. So there is no meaningful state variation
 * to exercise — ONE solid default-mount guard is the complete test (see note at (1)).
 *
 * Pattern-faithful to pages/__tests__/Home.mount.test.js / SuperAppHub.mount.test.js,
 * trimmed to what this page actually imports:
 *   - shallowMount (auto-stubs the AppIcon child) so the page's OWN setup() runs
 *   - useI18n mocked to return deterministic keys ({ t } is the ONLY destructure)
 *   - RouterLink provided as a pass-through GLOBAL stub (the page uses <RouterLink>
 *     as a global component; it does NOT import it from vue-router → no vue-router
 *     mock, no vi.hoisted stub needed)
 *   - real pinia in beforeEach: defensive scaffolding only — the page touches NO
 *     store, but this keeps the harness faithful to the proven template and ready
 *     if a store is ever added.
 *
 * lib/brand (BRAND_DOMAIN / DEMO_MENU_URL) is left REAL: it is pure env-var-backed
 * constants with static fallbacks (no side effects, no network), and asserting its
 * value reached the render proves the real import path resolved at setup.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatNumber: (v) => String(v),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// Real brand constants — the same values the page's setup() reads — so the mount
// assertion can confirm they actually flowed through to the rendered output.
import { BRAND_DOMAIN } from "../../lib/brand";
import DemoLanding from "../DemoLanding.vue";

const mountPage = () =>
  shallowMount(DemoLanding, {
    global: {
      stubs: {
        // Explicit pass-through so <RouterLink>'s slot (the "get my menu" CTA
        // label) actually renders — a bare auto-stub would swallow the slot.
        RouterLink: { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" },
      },
    },
  });

describe("DemoLanding — mount smoke", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  // ── (1) default mount — the core white-screen guard ─────────────────────────
  // setup() must not throw and the page's own hero must render. There is no state
  // variation on this static page, so this single case is the complete guard.
  it("mounts without a setup() crash and renders its hero", async () => {
    let wrapper;
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // Hero <h1> (home.heroTitle) + kicker (common.demo) — own-template keys,
    // returned verbatim by the mocked t → the hero block rendered.
    expect(text).toContain("home.heroTitle");
    expect(text).toContain("common.demo");
    // The RouterLink CTA slot label rendered (proves the pass-through stub worked).
    expect(text).toContain("home.getMyMenu");
    // The real lib/brand constant reached the render (import path resolved at setup).
    expect(text).toContain(BRAND_DOMAIN);
  });
});
