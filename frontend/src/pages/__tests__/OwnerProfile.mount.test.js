/**
 * Mount smoke test for OwnerProfile.vue (the owner restaurant-profile / settings
 * page — name, logo/cover, hours, contact, business type, colours; ~414 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined map
 * access, bad import) was never caught by a test". Mounting the page runs its real
 * <script setup> for real — the `tabs` computed, the route-driven `activeTab`, the
 * onMounted → loadOrderHandling(), and the `scheduleLocal = ref(_buildScheduleLocal())`
 * initializer that reads `tenant.meta` at setup time — so any such crash fails CI
 * here instead of white-screening in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerBilling.mount.test.js +
 * OwnerHome.mount.test.js + MarketplaceMenuPage.mount.test.js:
 *   - shallowMount + real pinia (setActivePinia(createPinia()) per test)
 *   - useI18n mocked to deterministic identity keys ({ t } — the page destructures
 *     ONLY t, verified against the source)
 *   - vue-router mocked (the page imports { useRoute, useRouter })
 *
 * API boundary (verified by reading the source, not assumed):
 *   - The page reads the profile from the TENANT STORE state (`tenant.meta`), NOT
 *     from a mount-time fetch: onMounted → loadOrderHandling() reads
 *     `tenant.meta?.profile`, and the scheduleLocal ref is seeded at setup from
 *     `tenant.meta?.profile?.business_hours_schedule`. The page never calls
 *     tenant.fetchMeta() at mount, so the loaded case seeds `tenant.meta` DIRECTLY
 *     (real pinia), exactly like OwnerBilling.mount.test.js.
 *   - The only network boundary is `profileApi.save()` from ../lib/onboardingApi,
 *     used solely in the two SAVE handlers (never at mount) — mocked defensively.
 *   - ../lib/api is mocked too (URL-routed empty default) as belt-and-suspenders:
 *     the dynamic child components (StepBrand / StepTheme / StepPublish /
 *     OwnerBilling / SecuritySettings) are shallow-stubbed so their setup never
 *     runs, but their modules are still imported.
 *
 * Route-driven tabs: `activeTab` is a computed off `route.query.tab` (falls back to
 * "profile"). A vi.hoisted mutable holder lets test 2 render the 'orders' tab — the
 * page's largest OWN template (the auto-accept / prep block + the business-hours
 * day-editor v-for) — with a seeded schedule.
 *
 * No intervals / observers / matchMedia / scrollIntoView / WebSocket at mount; the
 * two watch()es (activeTab-focus, meta-profile) are non-immediate so they do not
 * fire at mount. afterEach unmount is plain hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// The page destructures ONLY { t } from useI18n (verified). Identity keys.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// Direct network boundary: profileApi.save() — only ever called from the two save
// handlers, never at mount. Mocked so an accidental save can't hit the network.
vi.mock("../../lib/onboardingApi", () => ({
  profileApi: { save: vi.fn().mockResolvedValue({}) },
}));

// Defensive URL-routed api mock: nothing calls it at mount (children are stubbed),
// but their modules import ../lib/api. Empty default keeps any stray GET safe.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// The page imports { useRoute, useRouter } from vue-router. activeTab reads
// route.query.tab. A vi.hoisted holder (hoisted above the imports, so the mock
// factory can reference it without a TDZ "0 test" collection error) makes the
// route query mutable per-test so test 2 can render the 'orders' tab.
const routerState = vi.hoisted(() => ({ query: {} }));
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: routerState.query }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { useTenantStore } from "../../stores/tenant";
import OwnerProfile from "../OwnerProfile.vue";

const mountProfile = () =>
  shallowMount(OwnerProfile, {
    global: {
      stubs: {
        // Dynamic <component :is> children — stub explicitly so their real setup
        // never runs (belt-and-suspenders over shallowMount's auto-stubbing).
        StepBrand: true,
        StepTheme: true,
        StepPublish: true,
        OwnerBilling: true,
        SecuritySettings: true,
        AppIcon: true,
      },
    },
  });

describe("OwnerProfile — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // The tenant store's fetchMeta uses the localStorage-backed staleCache. The
    // page doesn't call fetchMeta at mount, so this is pure hygiene — but it keeps
    // one test's state from ever bleeding into the next.
    localStorage.clear();
    setActivePinia(createPinia());
    routerState.query = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No intervals/observers to leak, but unmount for clean teardown + to run the
    // watchers' stop, matching the other mount-smoke tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    routerState.query = {};
  });

  // ── (1) default mount: no tab query (→ 'profile' tab), empty tenant meta ───────
  // The core guard: setup() (tabs computed, activeTab, onMounted → loadOrderHandling
  // reading a null meta, the scheduleLocal initializer) and the always-rendered
  // header must render without throwing. tenant.meta is null → tenantName falls back
  // safely and every optional-chained meta read no-ops.
  it("mounts the default 'profile' tab with empty meta without a setup() crash", async () => {
    expect(() => {
      wrapper = mountProfile();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Always-rendered own-template header kicker — the crash-guard anchor.
    expect(wrapper.text()).toContain("common.profile");
  });

  // ── (2) loaded profile on the 'orders' tab: renders the biggest own template ───
  // Drives the page's largest OWN template (the inline auto-accept/prep block + the
  // business-hours day-editor v-for over scheduleLocal), which only renders when
  // activeTab === 'orders'. Seeding tenant.meta.profile.business_hours_schedule at
  // setup exercises _buildScheduleLocal() (both enabled + disabled day branches) and
  // loadOrderHandling() with real values — the exact paths that would crash on bad
  // data. tenant.meta.name drives the own-template h2.
  it("mounts the 'orders' tab with a loaded profile + schedule without a crash", async () => {
    routerState.query = { tab: "orders" };
    // meta is plain options-store state → settable directly (like OwnerBilling test).
    // The page reads it at setup, so seed BEFORE mounting.
    useTenantStore().meta = {
      name: "Testaurant",
      profile: {
        business_type: "restaurant",
        phone: "0612345678",
        auto_accept_orders: true,
        default_prep_minutes: 30,
        business_hours_schedule: {
          mon: { enabled: true, open: "09:00", close: "22:00" },
          sun: { enabled: false, open: null, close: null },
        },
      },
    };

    expect(() => {
      wrapper = mountProfile();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Loaded restaurant name from the own-template h2 (tenant.meta.name).
    expect(wrapper.text()).toContain("Testaurant");
    // The 'orders' tab's own inline template rendered (order-handling + hours).
    expect(wrapper.text()).toContain("orderHandling.title");
    expect(wrapper.text()).toContain("orderHandling.hoursTitle");
  });
});
