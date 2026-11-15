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

  // ── (4) marketplace commission card (D-10) ─────────────────────────────────
  // The dashboard aggregate already ships revenue_summary.marketplace /
  // .statement; the card must render them (7-day window, days=7 fetch) instead
  // of throwing them away. formatNumber is mocked to String(v), so the raw
  // figures render verbatim: revenue 1234.56, commission 123.45, net 1111.11.
  it("renders the marketplace commission card from the dashboard aggregate", async () => {
    _routes = {
      "/meta/": { data: { profile: { is_menu_published: true, is_open: true } } },
      "/owner/orders/": { data: { results: [], total: 0 } },
      "/owner/dashboard/": {
        data: {
          revenue_summary: {
            currency: "MAD",
            marketplace: { order_count: 13, revenue: "1234.56", commission_total: "123.45" },
            statement: {
              gross: "1234.56",
              promo_discounts: "0.00",
              loyalty_discounts: "0.00",
              tips: "0.00",
              commission: "123.45",
              net: "1111.11",
              refunds_issued: "0.00",
            },
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
    expect(text).toContain("ownerHome.marketplaceTitle");
    expect(text).toContain("ownerHome.marketplacePeriod");
    expect(text).toContain("13"); // marketplace order count
    expect(text).toContain("1234.56"); // marketplace revenue
    expect(text).toContain("123.45"); // marketplace commission
    expect(text).toContain("1111.11"); // marketplace net (revenue − commission)
  });
});

// ── S1-B (Run 8 G4a): B-02 drawer float input + B-03 revenue error tile ─────
// Appended — the four tests above are untouched. Imports below are hoisted by
// ESM, so `api` (the mocked lib/api) is usable here despite sitting at the
// end of the file.
import api from "../../lib/api";

describe("OwnerHome — S1-B: drawer float (B-02) + revenue error (B-03)", () => {
  let wrapper;

  // Closed-session drawer state: /current/ returns a session object (so the
  // card renders: drawerLoaded requires open || session) with the drawer
  // closed, plus a history whose newest session opened with a 120.00 float.
  const drawerRoutes = () => {
    _routes = {
      "/meta/": { data: { profile: { is_menu_published: true, is_open: true } } },
      "/owner/orders/": { data: { results: [], total: 0 } },
      "/owner/drawer/current/": {
        data: { open: false, session: { id: 7, status: "closed", opening_float: "120.00" } },
      },
      "/owner/drawer/history/": {
        data: { sessions: [{ id: 7, status: "closed", opening_float: "120.00" }] },
      },
    };
  };

  const openDrawerButton = () =>
    wrapper.findAll("button").find((b) => b.text().includes("cashDrawer.openDrawer"));

  const errorTileButton = () =>
    wrapper.findAll("button").find((b) => b.text().includes("ownerHome.tileError"));

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // Restore the URL-routed default get (a B-03 test below overrides it).
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
  });

  // ── B-02 ─────────────────────────────────────────────────────────────────
  it("prefills the opening-float input with the last float + shows the recommended-float hint", async () => {
    drawerRoutes();
    wrapper = mountHome();
    await flushPromises();
    await flushPromises(); // drain the nextTick-deferred drawer/history batch
    await flushPromises();

    const input = wrapper.find("#drawer-opening-float");
    expect(input.exists()).toBe(true);
    // Number() — a type="number" input may normalise "120.00" to "120".
    expect(Number(input.element.value)).toBe(120);
    // t() is mocked to echo the key (+ params), so assert the key + the
    // formatted recommended amount render together.
    expect(wrapper.text()).toContain("cashDrawer.recommendedFloatHint");
    expect(wrapper.text()).toContain("120");
  });

  it("posts the entered float when opening the drawer (not hardcoded 0.00)", async () => {
    drawerRoutes();
    wrapper = mountHome();
    await flushPromises();
    await flushPromises();
    await flushPromises();

    // setValue on the input (awaits a tick) — never set wrapper.vm state and
    // click a :disabled-bound button in the same tick (G3b lesson).
    await wrapper.find("#drawer-opening-float").setValue("75.50");
    await openDrawerButton().trigger("click");
    await flushPromises();

    const openCall = api.post.mock.calls.find(([url]) => url.includes("/owner/drawer/open/"));
    expect(openCall).toBeDefined();
    expect(openCall[1]).toEqual({ opening_float: "75.50" });
  });

  it("refuses a negative float client-side and posts nothing", async () => {
    drawerRoutes();
    wrapper = mountHome();
    await flushPromises();
    await flushPromises();
    await flushPromises();

    await wrapper.find("#drawer-opening-float").setValue("-5");
    await openDrawerButton().trigger("click");
    await flushPromises();

    expect(api.post.mock.calls.filter(([url]) => url.includes("/owner/drawer/open/"))).toHaveLength(0);
  });

  // ── B-03 ─────────────────────────────────────────────────────────────────
  it("shows the Retry tile (not a false 0 / MAD 0 strip) when /owner/dashboard/ fails", async () => {
    _routes = {
      "/meta/": { data: { profile: { is_menu_published: true, is_open: true } } },
      "/owner/orders/": { data: { results: [], total: 0 } },
    };
    api.get.mockImplementation((url) =>
      url.includes("/owner/dashboard/")
        ? Promise.reject(new Error("dashboard down"))
        : Promise.resolve(_match(url)),
    );

    wrapper = mountHome();
    await flushPromises();
    await flushPromises(); // drain the nextTick-deferred dashboard batch
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain("ownerHome.tileError");
    expect(errorTileButton().exists()).toBe(true);
    // The snapshot strip is replaced by the error tile — no revenue tile.
    expect(text).not.toContain("ownerHome.todayRevenue");
  });

  it("retries the dashboard from the error tile and renders the strip on success", async () => {
    const tz = "Africa/Casablanca";
    const dayStr = (d) =>
      new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
    const now = new Date();
    const yst = new Date();
    yst.setDate(yst.getDate() - 1);

    _routes = {
      "/meta/": { data: { profile: { is_menu_published: true, is_open: true, timezone: tz } } },
      "/owner/orders/": { data: { results: [], total: 0 } },
    };
    api.get.mockImplementation((url) =>
      url.includes("/owner/dashboard/")
        ? Promise.reject(new Error("dashboard down"))
        : Promise.resolve(_match(url)),
    );

    wrapper = mountHome();
    await flushPromises();
    await flushPromises();
    await flushPromises();
    expect(wrapper.text()).toContain("ownerHome.tileError");

    // Retry with the dashboard healthy again.
    _routes["/owner/dashboard/"] = {
      data: {
        revenue_summary: {
          currency: "MAD",
          daily: [
            { date: dayStr(yst), revenue: 50000, orders: 40 },
            { date: dayStr(now), revenue: 98765, orders: 42 },
          ],
        },
      },
    };
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    await errorTileButton().trigger("click");
    await flushPromises();
    await flushPromises();

    const text = wrapper.text();
    expect(text).not.toContain("ownerHome.tileError");
    expect(text).toContain("ownerHome.todayRevenue");
    expect(text).toContain("98765");
    expect(text).toContain("42");
  });

  it("renders the strip (no error tile) when the dashboard succeeds with no figures", async () => {
    _routes = {
      "/meta/": { data: { profile: { is_menu_published: true, is_open: true } } },
      "/owner/orders/": { data: { results: [], total: 0 } },
      "/owner/dashboard/": { data: {} },
    };

    wrapper = mountHome();
    await flushPromises();
    await flushPromises();
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain("ownerHome.todayRevenue");
    expect(text).not.toContain("ownerHome.tileError");
  });
});

describe("OwnerHome — G4b-E (B-31 tenant-tz today, B-35 translated time-ago)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // Defensive: the B-03 describe leaves a dashboard-rejecting mockImplementation
    // behind if it ever exits early — restore the default URL routing (the
    // file's own pattern, cf. the S1-B beforeEach).
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    // Freeze ONLY Date (timers/promises stay real, so flushPromises keeps
    // working): 2026-11-15T23:30:00Z is 2026-11-16 12:30 in Pacific/Auckland,
    // i.e. UTC "today" and tenant-tz "today" differ by design. (Africa/Casablanca
    // cannot be the example: Morocco is UTC in Nov 2026 per current tzdata —
    // DST ended 20 Sep 2026 — so its date equals the UTC date at this hour.)
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-15T23:30:00Z"));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    vi.useRealTimers();
  });

  // B-31: fetchTodayReservations must ask for the TENANT-tz date (2026-11-16),
  // not the UTC date (2026-11-15) — the old toISOString() call was off by one
  // near midnight local time.
  it("fetches today's reservations for the tenant-tz date, not the UTC date (B-31)", async () => {
    _routes = {
      "/meta/": { data: { profile: { is_menu_published: true, is_open: true, timezone: "Pacific/Auckland" } } },
      "/owner/orders/": { data: { results: [], total: 0 } },
    };

    wrapper = mountHome();
    await flushPromises();
    await flushPromises(); // drain the nextTick-deferred ratings/reservations/drawer batch
    await flushPromises();

    const resvCalls = api.get.mock.calls.filter(([url]) => url.includes("/owner/reservations/"));
    expect(resvCalls.length).toBeGreaterThan(0);
    expect(resvCalls[0][1].params.booked_for_date).toBe("2026-11-16");
  });

  // B-35: formatTimeAgo must render translated units via the ownerOrders keys,
  // never the raw "5m" / "2h" suffixes. The mocked t() returns the key verbatim
  // (params appended), so the assertions read the raw key path.
  it("renders recent-order ages with translated units, not raw m/h suffixes (B-35)", async () => {
    _routes = {
      "/meta/": { data: { profile: { is_menu_published: true, is_open: true, timezone: "Africa/Casablanca" } } },
      "/owner/orders/": {
        data: {
          results: [
            order({ id: 1, order_number: "A100", status: "confirmed", created_at: "2026-11-15T23:25:00.000Z" }),
            order({ id: 2, order_number: "A101", status: "confirmed", created_at: "2026-11-15T21:25:00.000Z" }),
          ],
          total: 2,
        },
      },
    };

    wrapper = mountHome();
    await flushPromises();
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain("ownerOrders.minutesAgo");
    expect(text).toContain("ownerOrders.hoursAgo");
    expect(text).not.toContain("5m");
    expect(text).not.toContain("2h");
  });
});
