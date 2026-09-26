/**
 * Mount smoke test for OwnerHome.vue (the owner dashboard home, ~1160 lines).
 *
 * WHY: this is the biggest, busiest owner surface and it had NO mount test. The
 * app's recurring production bug class is "a page white-screens on load because a
 * setup()-time error (TDZ, undefined map access, bad import) was never caught by
 * a test". OwnerHome is especially exposed: an async onMounted that awaits
 * Promise.all([tenant.fetchMeta(), order.fetchOrders()]), a nextTick-deferred
 * batch (ratings / reservations / drawer), a 30s background poll, a
 * visibilitychange listener, and a dozen order-derived computeds + template
 * v-fors (upcoming / active / pending / recent). Mounting runs all of that for
 * real, so a crash in any of it fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/MarketplaceMenuPage.mount.test.js +
 * pages/__tests__/SuperAppHub.mount.test.js (URL-routed api mock):
 *   - shallowMount (auto-stubs the heavy dashboard children: OwnerDashboardAlerts,
 *     OwnerDashboardReadiness, OwnerDashboardDishPanel, OwnerNextAction,
 *     BusyModeControl, AppIcon)
 *   - real pinia (order / tenant / toast stores run for real) + a mocked lib/api
 *   - useI18n + vue-router mocked
 *
 * The useNowTicker + useConfirmModal composables and the ownerLiveFocus/staleCache
 * libs are left REAL: they are jsdom-safe (staleCache falls through to the mocked
 * network on an empty cache; every meta getter is optional-chained) and each of
 * the two 30s intervals (the page poll + useNowTicker) is cleared on unmount — so
 * afterEach unmounts to keep timers from leaking between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatNumber: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires several GETs (/meta/, /owner/orders/, then
// deferred /owner/ratings/, /owner/reservations/, /owner/drawer/current/).
// Default: everything resolves empty so the fresh-owner path renders. Tests set
// _routes to drive the loaded path.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// OwnerHome imports { RouterLink, useRouter } from 'vue-router'.
// vi.hoisted: the vi.mock('vue-router') factory below is hoisted above the imports
// and runs during import evaluation — before a plain `const` in the file body would
// initialize — so referencing a plain const there hits the TDZ ("0 test" collection
// error). vi.hoisted makes the stub available to the hoisted factory.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OwnerHome from "../OwnerHome.vue";

const mountHome = () =>
  shallowMount(OwnerHome, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

const order = (overrides = {}) => ({
  id: 1,
  order_number: "A100",
  status: "confirmed",
  fulfillment_type: "delivery",
  currency: "MAD",
  total: "50.00",
  scheduled_for: null,
  created_at: new Date().toISOString(),
  status_updated_at: new Date().toISOString(),
  ...overrides,
});

describe("OwnerHome — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // tenant.fetchMeta() uses the REAL staleCache (localStorage-backed). Without
    // this clear, test 1's empty-meta write ({}) is served from cache to test 2
    // (still "fresh" within the 5-min TTL), so test 2 never sees its /meta/ mock
    // payload and its profile-driven computeds read the stale empty meta.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // OwnerHome registers a 30s poll interval + useNowTicker's 30s interval;
    // unmount runs onUnmounted → clearInterval so no timer leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) fresh owner: empty meta + no orders ───────────────────────────────
  // The core guard: the async onMounted (fetchMeta + fetchOrders + the deferred
  // batch) and the whole template must render with empty data and not throw.
  it("mounts a fresh owner (empty meta / no orders) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountHome();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerHome.title");
    expect(wrapper.text()).toContain("ownerHome.kicker");
    // Empty profile → is_menu_published falsey → draft chip.
    expect(wrapper.text()).toContain("ownerHome.draft");
  });

  // ── (2) published, open restaurant with active orders ─────────────────────
  // Drives the profile-computed branches (published / open / menu-active /
  // accepting-delivery) AND the order-derived computeds + template v-fors
  // (activeOrders / pendingOrders / upcoming / recent + the per-order date math),
  // the exact own-template paths that only run with a non-empty orders array.
  it("mounts a published, open restaurant with active + pending orders without a crash", async () => {
    _routes = {
      "/meta/": {
        data: {
          profile: {
            is_menu_published: true,
            is_open: true,
            delivery_enabled: true,
            is_menu_temporarily_disabled: false,
          },
        },
      },
      "/owner/orders/": {
        data: {
          results: [
            order({ id: 1, order_number: "A100", status: "confirmed" }),
            order({ id: 2, order_number: "A101", status: "pending" }),
          ],
          total: 2,
        },
      },
    };

    expect(() => {
      wrapper = mountHome();
    }).not.toThrow();

    await flushPromises();
    await flushPromises(); // drain the nextTick-deferred ratings/reservations/drawer batch

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerHome.title");
    // Published profile → published chip (not draft).
    expect(wrapper.text()).toContain("ownerHome.published");
  });

  // ── (3) Today's realized KPIs come from the /owner/dashboard/ aggregate ────
  // Regression guard: OwnerHome used to derive today's revenue / order count /
  // avg ticket by summing order.orders — the ACTIVE-only store, which drops
  // COMPLETED orders (they fall out ~30s after completion) and over-counts
  // still-PENDING ones — so the headline numbers decayed toward zero through
  // service and disagreed with OwnerAnalytics. The realized figures must instead
  // read revenue_summary.daily from GET /owner/dashboard/ (billable statuses
  // incl. COMPLETED, tenant-tz bucketed). formatNumber is mocked to String(v),
  // so the raw daily figures render verbatim and are asserted directly.
  it("sources today's revenue + order count from the dashboard aggregate, not the active order store", async () => {
    const tz = "Africa/Casablanca";
    const dayStr = (d) =>
      new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
    const now = new Date();
    const yst = new Date();
    yst.setDate(yst.getDate() - 1);

    _routes = {
      "/meta/": { data: { profile: { is_menu_published: true, is_open: true, timezone: tz } } },
      // Active store holds only a live pending order — summing it could never
      // produce the aggregate's 98765 / 42, so the assertions below prove the
      // realized figures are NOT store-derived.
      "/owner/orders/": {
        data: { results: [order({ id: 9, order_number: "A900", status: "pending", total: "77.00" })], total: 1 },
      },
      // Authoritative realized aggregate for today + yesterday.
      "/owner/dashboard/": {
        data: {
          revenue_summary: {
            currency: "MAD",
            daily: [
              { date: dayStr(yst), revenue: 50000, orders: 40 },
              { date: dayStr(now), revenue: 98765, orders: 42 },
            ],
          },
        },
      },
    };

    expect(() => {
      wrapper = mountHome();
    }).not.toThrow();

    await flushPromises();
    await flushPromises(); // drain the nextTick-deferred batch (incl. /owner/dashboard/)
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain("98765"); // today's revenue from revenue_summary.daily
    expect(text).toContain("42");    // today's order count from revenue_summary.daily
    // The live-queue pending tile still reflects the store's pending order.
    expect(text).toContain("ownerOrders.todayPending");
  });
});
