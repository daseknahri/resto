/**
 * Mount smoke test for WaiterPage.vue (the waiter / dine-in service page, ~2637 lines).
 *
 * WHY: this is one of the largest, busiest staff surfaces and it had NO mount
 * test. The app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined map access, bad import) was never
 * caught by a test". WaiterPage is especially exposed: an async onMounted that
 * awaits Promise.all([waiter.fetchOrders(), loadTableStatuses(), loadMyShift()]),
 * a menu-prefetch, a 15s background poll, a visibilitychange listener, three
 * focus-trap watchers, and a dozen order-derived computeds + template v-fors
 * (table grouping, floor tiles, tabs). The page's EXTRACTED CHILD components
 * (WaiterOrderCard, WaiterSettleSheet, …) and the waiter STORE each have tests,
 * but nothing mounted the PAGE's own setup() until this file. shallowMount runs
 * WaiterPage's real setup() while auto-stubbing the heavy children, so a crash in
 * any of it fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * SuperAppHub.mount.test.js (URL-routed api mock). WaiterPage imports NOTHING
 * from vue-router (it uses plain <a> links), so vue-router is intentionally NOT
 * mocked and no route param is supplied.
 *
 * The install-prompt / wake-lock / now-ticker / confirm-modal composables are
 * left REAL: they are jsdom-safe (feature-detected navigator APIs, optional-
 * chained window.matchMedia), and each of the two setInterval timers (the 15s
 * page poll + useNowTicker's 30s ticker) is cleared on unmount — so afterEach
 * unmounts to keep timers from leaking between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// WaiterPage destructures exactly { t, formatDateTime, currentLocale } from
// useI18n(). `currentLocale` MUST be a ref-like ({ value }) — the page reads
// currentLocale.value inside fmtOrderPrice / billDateTime / shiftRevenue. The
// mocked `t` returns its key verbatim (param-less) so own-template headings are
// assertable by key.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: () => "",
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires several GETs (/staff/orders/, /staff/tables/,
// /staff/my-shift/, plus menu.fetchCategories → /categories/). Default: everything
// resolves empty so the no-orders path renders. Tests set _routes to drive the
// loaded path. _match / _routes are read ONLY inside the lazy vi.fn closures.
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

// idempotency is imported transitively by the waiter store.
vi.mock("../../lib/idempotency", () => ({
  newIdempotencyKey: () => "test-idem-key",
}));

import WaiterPage from "../WaiterPage.vue";

const mountPage = () =>
  shallowMount(WaiterPage, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

const tableOrder = (overrides = {}) => ({
  id: 1,
  order_number: "A100",
  status: "pending",
  fulfillment_type: "table",
  table_label: "Table 5",
  currency: "MAD",
  total: "120.00",
  items: [],
  created_at: new Date().toISOString(),
  status_updated_at: new Date().toISOString(),
  ...overrides,
});

describe("WaiterPage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // localStorage FIRST: the page (firstRun / sound keys) and menu.fetchCategories'
    // staleCache are localStorage-backed, so a leaked write from a prior test would
    // change what this test's fresh mount sees.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // onMounted arms a 15s poll setInterval and useNowTicker a 30s ticker;
    // unmount runs onUnmounted → clearInterval so no timer leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) no orders: the core setup()/onMounted crash guard ─────────────────
  // The async onMounted (fetchOrders + loadTableStatuses + loadMyShift + the
  // poll/visibility wiring) and the whole template must render with empty data
  // and not throw.
  it("mounts and runs the real setup() + onMounted wiring without throwing", async () => {
    // The white-screen bug class throws synchronously inside setup(), so mount()
    // itself would throw — this assertion is the guard.
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    // Let onMounted's fetchOrders / loadTableStatuses / loadMyShift settle.
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // With no orders the page's OWN template renders the empty state (default tab
    // is "needs_action", not "recent"). The mocked t() returns the key verbatim.
    expect(wrapper.text()).toContain("waiterPage.noActiveOrders");
  });

  // ── (2) loaded, table-grouped board ───────────────────────────────────────
  // Two active dine-in orders on the same table drive the table-grouping computed
  // + own-template group header (label, tableStatus badge, order count, total via
  // fmtOrderPrice/settleOutstanding) — the exact own-template paths that only run
  // with a non-empty orders array. Both statuses (pending/ready) fall in the
  // default "needs_action" tab, so they are visible immediately.
  it("renders a loaded, table-grouped board without crashing", async () => {
    _routes = {
      "/staff/orders/": {
        data: {
          count: 2,
          results: [
            tableOrder({ id: 1, order_number: "A100", status: "pending" }),
            tableOrder({ id: 2, order_number: "A101", status: "ready", total: "80.00" }),
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    const text = wrapper.text();
    // Own-template group header (NOT text inside the stubbed WaiterOrderCard).
    expect(text).toContain("Table 5");
    expect(text).toContain("waiterPage.tableTotal");
    // The empty state must be gone once orders are present.
    expect(text).not.toContain("waiterPage.noActiveOrders");
  });
});
