/**
 * Mount smoke test for Home.vue (the customer landing page, ~442 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, unguarded browser API)
 * was never caught by a test". Mounting the page runs its real setup() + first
 * render — so any such crash fails CI here instead of in production.
 *
 * REGRESSION GUARD (#94): this page white-screened in prod when the service grid
 * did `ACCENT_CLASSES[svc.accent].tile` UNGUARDED and a service accent had no map
 * entry. The code is now guarded (`?.tile ?? fallback`), but this test mounts the
 * page so the service-verticals grid is rendered over EVERY real service accent
 * from the real lib/services registry — so a regression back to an unguarded
 * undefined-map lookup fails CI.
 *
 * Pattern-faithful to pages/__tests__/SuperAppHub.mount.test.js:
 *   - shallowMount (auto-stubs the AppIcon child) so the page's OWN setup() runs
 *   - real pinia (setActivePinia(createPinia())) + a mocked lib/api (the session
 *     store imports it) + a stubbed global fetch (lib/pricing.fetchPlanPricing)
 *   - useI18n mocked to return deterministic keys
 *   - vue-router mocked (Home calls useRoute/useRouter)
 *
 * lib/services (SERVICES) and lib/pricing (fetchPlanPricing / PRICING_PLANS) are
 * left REAL: the verticals v-for indexes the page's ACCENT_CLASSES map for all six
 * real accents (the crash path this guard exists to catch), and the plans computed
 * runs against the real pricing scaffold.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
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

// The session store (pulled in transitively) imports lib/api at module load and
// calls it inside actions. Default everything to empty so nothing hits the network.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// Home imports ONLY { useRoute, useRouter } from vue-router (NOT RouterLink — that
// is used in the template as a global component + a dynamic <component :is="'RouterLink'">,
// both covered by the global stub below, so no vi.hoisted RouterLink stub is needed).
// route.query IS read at setup (`leadSuccess = ref(route.query.lead === 'success')`),
// so expose a hoisted mutable the factory reads and individual tests seed before mount.
const routeState = vi.hoisted(() => ({ query: {}, params: {} }));
vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { useSessionStore } from "../../stores/session";
import Home from "../Home.vue";

const mountHome = () =>
  shallowMount(Home, {
    global: {
      stubs: {
        // Explicit pass-through stubs so slot content (service tiles, the lead
        // banner) actually renders — the tile/pill nodes are where the
        // ACCENT_CLASSES lookups run.
        RouterLink: { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
      },
    },
  });

describe("Home — mount smoke", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    routeState.query = {};
    routeState.params = {};
    // lib/pricing.fetchPlanPricing() runs in onMounted via global fetch. Stub it so
    // the mount is deterministic and never touches the network. (It is already
    // try/caught to {} on failure, but stubbing keeps the test hermetic.)
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) }))
    );
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    routeState.query = {};
  });

  // ── (1) guest / default render — the #94 undefined-map regression guard ─────
  // setup() must not throw, and the verticals grid must render. The grid's v-for
  // over the real SERVICES registry indexes ACCENT_CLASSES for every real accent
  // (amber/indigo/emerald/rose/sky/violet) — the exact lookup that white-screened
  // prod when it was unguarded.
  it("mounts for a guest without a setup() crash and renders the service grid", async () => {
    let wrapper;
    expect(() => {
      wrapper = mountHome();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // Verticals section heading (home.verticalsTitle — own-template key, verbatim
    // via the mocked t) → the accent-mapped grid section rendered.
    expect(text).toContain("home.verticalsTitle");
    // The per-live-service CTA pill (home.verticalCta) renders only inside a live
    // service tile — so its presence proves the live tiles (and their
    // ACCENT_CLASSES[svc.accent] tile+pill lookups) actually rendered.
    expect(text).toContain("home.verticalCta");
    // Guest: no lead-success banner, no owner "open workspace" entry point.
    expect(text).not.toContain("home.leadSuccess");
    expect(text).not.toContain("home.openWorkspace");
  });

  // ── (2) lead=success query + authenticated tenant owner ─────────────────────
  // The page's real state variation: the ?lead=success banner branch (inside the
  // <Transition>) and the owner-gated "open workspace" link (session.canEditTenantMenu).
  // Seed both and assert their branches render — with setup() still not throwing.
  it("mounts with lead=success + an owner session (banner + workspace link render)", async () => {
    routeState.query = { lead: "success" };
    // canEditTenantMenu getter reads user.can_edit_tenant_menu === true.
    useSessionStore().user = { can_edit_tenant_menu: true, role: "tenant_owner" };

    let wrapper;
    expect(() => {
      wrapper = mountHome();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // ?lead=success → the success banner branch rendered.
    expect(text).toContain("home.leadSuccess");
    // Owner session → the "open workspace" entry point rendered.
    expect(text).toContain("home.openWorkspace");
    // Grid still renders in this state (accent lookups exercised again).
    expect(text).toContain("home.verticalsTitle");
  });
});
