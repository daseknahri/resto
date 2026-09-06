/**
 * Mount smoke test for OwnerAnalytics.vue (the owner analytics / insights page, ~337 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API) was never caught by a test". OwnerAnalytics reads a localStorage-backed
 * period preference at setup(), fires order.fetchOrders() in onMounted, and drives
 * a dozen revenue/order-derived computeds (todayStats / yesterdayStats / avgTicket /
 * three sparkline series / chartDays) plus tenant.capabilities + session.canViewRevenue
 * template gates. Mounting runs all of that for real, so a crash in setup() or the
 * initial render fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * pages/__tests__/SuperAppHub.mount.test.js (URL-routed api mock + real pinia):
 *   - shallowMount (auto-stubs the heavy children: OwnerDashboardInsights,
 *     OwnerDashboardRevenue, RepeatAnalyticsWidget, BestSellersWidget,
 *     RevenueBarChart, SparklineChart, AppIcon)
 *   - real pinia (order / tenant / session / toast stores run for real) + a mocked lib/api
 *   - useI18n mocked to exactly { t, formatNumber } (the page's real destructure)
 *   - vue-router mocked (the page imports { RouterLink })
 *
 * DATA-FLOW NOTE (why case 2 drives a child emit, not an api route):
 *   The page itself only GETs /owner/orders/ at mount (via order.fetchOrders()).
 *   The analytics/dashboard payload is owned by the child <OwnerDashboardInsights>,
 *   which shallowMount stubs — so it never fetches and never emits. Its @data emit
 *   is also the ONLY thing that flips insightsLoading false (revealing the real KPI
 *   cards past the loading skeleton). So the faithful "loaded" case simulates that
 *   child by emitting the analytics payload from the stub — exercising onInsightsData
 *   + every revenue/order-derived computed (todayStats revenue/count, avgTicket,
 *   sparklines, chartDays). The CSV-export GET (/owner/analytics/export/) is on a
 *   button click, not at mount, so it is never hit here.
 *
 * NO CHART LIBRARY: SparklineChart + RevenueBarChart are pure inline-SVG Vue
 * components (no chart.js / canvas / dynamic import) and are auto-stubbed by
 * shallowMount, so nothing chart-related inits at mount — no mock needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // t returns the key verbatim (params, when present, are appended so the raw
    // key path is still asserted-on). formatNumber is a plain stringify — the page
    // wraps every call in try/catch and only reads the returned string.
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatNumber: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: the only GET at mount is /owner/orders/ (order.fetchOrders,
// ?mode=active). Default: everything resolves { data: {} } so the empty/cold path
// renders. Tests set _routes to drive the loaded orders path.
// _routes/_match are plain (not vi.hoisted): they are only read lazily inside the
// vi.fn callback when api.get actually fires at mount — never during the hoisted
// factory's own evaluation — so there is no TDZ.
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

// OwnerAnalytics imports { RouterLink } from 'vue-router' (static binding used for
// the Pending + Reservations KPI cards).
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

import OwnerAnalytics from "../OwnerAnalytics.vue";
// Imported only to target the stubbed insights child for the @data emit in case 2.
import OwnerDashboardInsights from "../../components/OwnerDashboardInsights.vue";

const mountPage = () =>
  shallowMount(OwnerAnalytics, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("OwnerAnalytics — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // The page reads a localStorage-backed period preference at setup() and the
    // tenant store's fetchMeta path is staleCache-backed; clear so no cross-test
    // localStorage state leaks into the next mount.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // The page registers no interval/observer/WebSocket at mount, but unmount as
    // hygiene so a watcher can't observe state across tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) empty / default mount ──────────────────────────────────────────────
  // The core guard: the setup() localStorage read + onMounted fetchOrders() and the
  // whole loading-skeleton template must render with empty data and not throw.
  it("mounts with empty data (cold owner) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered, outside every v-if) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerAnalytics.title");
    expect(wrapper.text()).toContain("ownerAnalytics.kicker");
    // No insights emit yet → insightsLoading stays true → the KPI skeleton branch
    // rendered (aria-busy reflects it). Proves the loading path is crash-free.
    expect(wrapper.attributes("aria-busy")).toBe("true");
  });

  // ── (2) loaded state: pending orders + a realistic analytics payload ───────
  // Routes /owner/orders/ so order.fetchOrders() populates the pending count, then
  // simulates the <OwnerDashboardInsights> child by emitting the analytics @data
  // payload — flipping insightsLoading false and driving onInsightsData + every
  // revenue/order-derived computed (todayStats revenue/count, avgTicket, the three
  // sparkline series, chartDays), the own-template paths that only run once loaded.
  it("mounts a loaded analytics state (pending orders + revenue payload) without a crash", async () => {
    _routes = {
      "/owner/orders/": {
        data: {
          results: [
            { id: 1, status: "pending" },
            { id: 2, status: "confirmed" },
          ],
          total: 2,
        },
      },
    };

    // _fmtDate() falls back to Date.toDateString() here (tenant.resolvedMeta is null
    // in the test env → no timezone), so the daily entries must key off toDateString()
    // for todayStats/yesterdayStats to find them.
    const now = new Date();
    const todayKey = now.toDateString();
    const yst = new Date(now);
    yst.setDate(yst.getDate() - 1);
    const ystKey = yst.toDateString();

    const insightsPayload = {
      today_reservations: 4,
      today_new_reservations: 2,
      revenue_summary: {
        currency: "MAD",
        daily: [
          { date: "2026-09-02", revenue: 600, orders: 6 },
          { date: "2026-09-03", revenue: 720, orders: 7 },
          { date: "2026-09-04", revenue: 900, orders: 9 },
          { date: ystKey, revenue: 800, orders: 8 },
          { date: todayKey, revenue: 1234, orders: 10 },
        ],
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // order.fetchOrders() resolves → order.orders populated

    // Simulate the stubbed insights child emitting its dashboard payload.
    const insights = wrapper.findComponent(OwnerDashboardInsights);
    expect(insights.exists()).toBe(true);
    insights.vm.$emit("data", insightsPayload);
    await flushPromises(); // onInsightsData ran → insightsLoading false, revenueSummary set

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerAnalytics.title");
    // insightsLoading flipped false → the real KPI grid replaced the skeleton.
    expect(wrapper.attributes("aria-busy")).toBe("false");
    expect(wrapper.text()).toContain("ownerHome.todayRevenue");
    // todayStats.revenue = formatNumber(1234) = "1234" (mock stringify) → proves the
    // daily-entry match + the revenue computed ran and rendered.
    expect(wrapper.text()).toContain("1234");
    // Pending KPI: todayStats.pending = 1 (> 0) → the amber "view all orders"
    // RouterLink branch rendered from the fetched orders.
    expect(wrapper.text()).toContain("ownerOrders.todayPending");
    expect(wrapper.text()).toContain("ownerHome.viewAllOrders");
  });
});
