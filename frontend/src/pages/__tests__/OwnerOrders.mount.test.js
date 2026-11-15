/**
 * Mount smoke test for OwnerOrders.vue (the owner live order-management board, ~2455 lines).
 *
 * WHY: this is the single busiest owner surface and it had NO mount test. The app's
 * recurring production bug class is "a page white-screens on load because a setup()-time
 * error (TDZ, undefined map access, an unguarded browser API) was never caught by a test".
 * OwnerOrders is heavily exposed: a `<script setup>` with ~1100 lines of refs / computeds /
 * helpers, a module-level `window.addEventListener('click', …)` audio primer, a
 * localStorage-backed sound preference read at setup, a `usePrintTicket()` call, an
 * async onMounted (requestNotificationPermission → order.fetchOrders → seed86Count →
 * visibilitychange listener → realtime connect → self-rescheduling poll), TWO background
 * intervals (a 30s age-tick + useNowTicker's 30s tick) plus a self-rescheduling 15s poll
 * timeout, and a dozen order-derived computeds + template v-fors. Mounting runs all of that
 * for real, so a crash in any of it fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js (URL-routed api mock):
 *   - shallowMount (auto-stubs the heavy children: OwnerOrdersTrackModal, OwnerOrders86Board,
 *     OwnerOrdersFilterSheet, OwnerOrdersCashierModal, AppIcon)
 *   - real pinia (order / toast / tenant stores run for real) + a mocked lib/api
 *   - useI18n + vue-router mocked
 *
 * Left REAL (jsdom-safe, matching OwnerHome): useNowTicker, useConfirmModal, usePrintTicket
 * (a pure factory — only touches the DOM when a print button is clicked), ownerLiveFocus
 * (pure fns), and the order/toast/tenant stores. tenant.capabilities is a getter with a full
 * default so `tenant.capabilities.tables` is always safe even with meta === null.
 *
 * Mocked (a NETWORK/ENV boundary, exactly like lib/api and vue-router): useOwnerRealtime.
 * The page calls `ordersRealtime.connect()` at mount; the real composable opens a live
 * WebSocket to `wss://<host>/ws/owner/` and schedules reconnect timers — a real network side
 * effect that would make the test non-hermetic. The stub keeps the page's OWN realtime wiring
 * (the `useOwnerRealtime(cb)` registration, the onMounted connect / onUnmounted disconnect,
 * and the `connectionState?.value === 'live'` poll-cadence read) fully exercised.
 *
 * NOT stubbed (verified from source, so noted here for the next reader):
 *   - AudioContext — created LAZILY (inside _getAudioCtx, called only from playAlertSound or
 *     the first-click primer). checkForNewOrders() seeds knownOrderIds and returns on FIRST
 *     load without playing a sound, so NO AudioContext is constructed at mount. jsdom has none;
 *     the whole path is try/caught anyway.
 *   - Notification — the onMounted requestNotificationPermission() (and showBrowserNotification)
 *     both guard on `"Notification" in window`, which is false in jsdom → they short-circuit.
 *   - navigator.clipboard — only touched in click handlers, never at mount.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in OwnerOrders is { t, itemCountLabel, formatNumber, formatDateTime,
// currentLocale } — the mock MUST return all five or setup throws on the destructure.
// (formatCurrency is a LOCAL helper in the page that wraps formatNumber, so it needs no mock.)
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k, // key verbatim → assertions read the raw key
    itemCountLabel: (v) => String(v),
    formatNumber: (v) => String(v),
    formatDateTime: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires GETs (/owner/orders/ via the order store, then
// /dishes/ via seed86Count). Default: everything resolves empty so the fresh-owner path
// renders. Tests set _routes to drive the loaded path. (_match is a plain const — it is only
// referenced from inside the lazy vi.fn closures below, never from a hoisted factory, so no TDZ.)
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

// useOwnerRealtime is a network boundary (a live WebSocket). Stub it so connect()/disconnect()
// are no-ops and connectionState is inert. The page reads `connectionState?.value === 'live'`
// in its poll scheduler, so the stub must expose a `.value`.
vi.mock("../../composables/useOwnerRealtime", () => ({
  useOwnerRealtime: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    connected: { value: false },
    connectionState: { value: "idle" },
  }),
}));

// OwnerOrders imports { RouterLink, useRoute } from 'vue-router'.
// vi.hoisted: the vi.mock('vue-router') factory below is hoisted above the imports and runs
// during import evaluation — before a plain `const` in the file body would initialize — so a
// plain const referenced there hits the TDZ ("0 test" collection error). vi.hoisted makes the
// stub available to the hoisted factory.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OwnerOrders from "../OwnerOrders.vue";

const mountOrders = () =>
  shallowMount(OwnerOrders, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// A minimal-but-realistic active order carrying exactly the fields the active-board card and
// its computeds read (order_number, status, fulfillment_type, currency, total, created_at,
// items_count, customer_name, payment_status). Deliberately omits the heavy nested objects
// (delivery_job, customer_trust, scheduled_for) so the row stays on its simple render path.
const order = (overrides = {}) => ({
  id: 1,
  order_number: "A100",
  status: "confirmed",
  fulfillment_type: "delivery",
  currency: "MAD",
  total: "82.50",
  created_at: new Date().toISOString(),
  scheduled_for: null,
  payment_status: "unpaid",
  customer_name: "Sara",
  items_count: 2,
  items: [{ dish_name: "Burger", qty: 2, subtotal: "82.50" }],
  ...overrides,
});

describe("OwnerOrders — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // The sound preference reads localStorage at setup (SOUND_KEY). Clear it first so no
    // stale value bleeds between tests (mirrors the staleCache clear in OwnerHome's beforeEach).
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // OwnerOrders registers a 30s age-tick interval, useNowTicker's 30s interval, AND a
    // self-rescheduling 15s poll setTimeout; unmount runs onUnmounted → clearInterval /
    // clearTimeout / realtime.disconnect so no timer leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) empty board: no orders ────────────────────────────────────────────
  // The core guard: the whole `<script setup>` + the async onMounted (fetchOrders +
  // seed86Count + realtime.connect + scheduleNextPoll) + the full template must render
  // with empty data and NOT throw.
  it("mounts an empty board (no orders) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountOrders();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerOrders.title");
    expect(wrapper.text()).toContain("ownerOrders.kicker");
    // Active tab (default) + empty orders → the "no orders yet" empty state renders.
    expect(wrapper.text()).toContain("ownerOrders.noOrdersYet");
  });

  // ── (2) loaded board with active orders ───────────────────────────────────
  // Drives the order-derived computeds + template v-for (filteredOrders / statusTabs /
  // todayStats + the per-order age/date/currency math + statusLabel/statusClass/
  // fulfillmentLabel/formatTime/itemCountLabel) — the own-template paths that only run
  // with a non-empty orders array.
  it("mounts a loaded board with active orders without a crash", async () => {
    _routes = {
      "/owner/orders/": {
        data: {
          results: [
            order({ id: 1, order_number: "A100", status: "confirmed" }),
            order({ id: 2, order_number: "A101", status: "pending", fulfillment_type: "pickup", customer_name: "Omar" }),
          ],
          total: 2,
        },
      },
    };

    expect(() => {
      wrapper = mountOrders();
    }).not.toThrow();

    await flushPromises();
    await flushPromises(); // drain the non-blocking seed86Count() fired after the order fetch

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerOrders.title");
    // Order rows rendered (order_number is own-template literal content, only present with a
    // non-empty list) → the v-for + per-order computeds all ran.
    expect(wrapper.text()).toContain("A100");
    expect(wrapper.text()).toContain("A101");
    // A confirmed order's status chip → statusLabel('confirmed') → the mocked t echoes the key.
    expect(wrapper.text()).toContain("ownerOrders.statusConfirmed");
    // The empty state must be gone now that the board has orders.
    expect(wrapper.text()).not.toContain("ownerOrders.noOrdersYet");
  });
});

// ── S1-A (B-01 / B-04) — appended by Run 8 Surface 1, cluster S1-A ─────────────
// Imports are hoisted, so these resolve to the same (mocked api / real
// useConfirmModal) modules as the imports at the top of the file.
import api from "../../lib/api";
import { useConfirmModal } from "../../composables/useConfirmModal";

// Today's date exactly the way the page buckets it with no tenant timezone set
// (device-local YYYY-MM-DD, matching _tenantDayIso in OwnerOrders.vue).
const _todayStr = () =>
  new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());

// The header stats bar renders exactly three `p.text-2xl` cells, in order:
// [today count, today revenue, today pending]. (The h1 title is an h1, not a p,
// and the stubbed children render no text-2xl cells.)
const _statsCells = (w) => w.findAll("p.text-2xl");

describe("OwnerOrders — S1-A (B-01 today figures / B-04 bulk confirms)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── B-01: dashboard aggregate wins over the decaying active list ─────────
  it("B-01: header today count/revenue come from the dashboard aggregate, not the active list", async () => {
    _routes = {
      "/owner/orders/": {
        data: {
          results: [
            order({ id: 1, order_number: "A100", status: "confirmed", total: "100.00" }),
            order({ id: 2, order_number: "A101", status: "pending", total: "65.00", fulfillment_type: "pickup", customer_name: "Omar" }),
          ],
          total: 2,
        },
      },
      // A completed order already left the active list, so the dashboard sees 7
      // orders / 1234.5 revenue while the client calc would see 2 / 165.
      "/owner/dashboard/": {
        data: { revenue_summary: { currency: "MAD", daily: [{ date: _todayStr(), revenue: 1234.5, orders: 7 }] } },
      },
    };

    wrapper = mountOrders();
    await flushPromises();
    await flushPromises();
    await flushPromises(); // drain the non-blocking fetchTodaySummary() fired on mount

    const stats = _statsCells(wrapper);
    expect(stats.length).toBe(3);
    expect(stats[0].text()).toBe("7"); // dashboard orders, not the 2 loaded
    expect(stats[1].text()).toBe("1234.5"); // dashboard revenue, not 165
    expect(stats[2].text()).toBe("1"); // pending still comes from the live list
  });

  it("B-01: falls back to the client calc when the dashboard has no entry for today", async () => {
    _routes = {
      "/owner/orders/": {
        data: {
          results: [
            order({ id: 1, order_number: "A100", status: "confirmed", total: "100.00" }),
            order({ id: 2, order_number: "A101", status: "pending", total: "65.00", fulfillment_type: "pickup", customer_name: "Omar" }),
          ],
          total: 2,
        },
      },
      "/owner/dashboard/": { data: { revenue_summary: { currency: "MAD", daily: [] } } },
    };

    wrapper = mountOrders();
    await flushPromises();
    await flushPromises();
    await flushPromises();

    const stats = _statsCells(wrapper);
    expect(stats.length).toBe(3);
    expect(stats[0].text()).toBe("2"); // client calc: 2 loaded orders
    expect(stats[1].text()).toBe("165"); // client calc: 100 + 65
    expect(stats[2].text()).toBe("1");
  });

  // ── B-04: confirm-all-pending ────────────────────────────────────────────
  const _mountTwoPending = async () => {
    _routes = {
      "/owner/orders/": {
        data: {
          results: [
            order({ id: 1, order_number: "A100", status: "pending" }),
            order({ id: 2, order_number: "A101", status: "pending", fulfillment_type: "pickup", customer_name: "Omar" }),
          ],
          total: 2,
        },
      },
    };
    wrapper = mountOrders();
    await flushPromises();
    await flushPromises();
    const btn = wrapper.findAll("button").find((b) => b.text().includes("ownerOrders.confirmAllPending"));
    expect(btn.exists()).toBe(true);
    return btn;
  };

  it("B-04: confirm-all-pending asks first and posts the explicit ids only after approval", async () => {
    const btn = await _mountTwoPending();
    await btn.trigger("click");
    await flushPromises();
    // No POST before the owner approves the confirm dialog.
    expect(api.post).not.toHaveBeenCalledWith("/owner/orders/bulk-status/", expect.anything());
    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();
    expect(api.post).toHaveBeenCalledWith("/owner/orders/bulk-status/", {
      order_ids: [1, 2],
      status: "confirmed",
    });
  });

  it("B-04: declining the confirm-all dialog posts nothing", async () => {
    const btn = await _mountTwoPending();
    await btn.trigger("click");
    await flushPromises();
    useConfirmModal()._settle(false);
    await flushPromises();
    expect(api.post).not.toHaveBeenCalled();
  });

  // ── B-04: 86-board reset-all (via the stubbed board's reset-all event) ────
  it("B-04: 86 reset-all confirms with the sold-out count and posts the explicit dish ids", async () => {
    _routes = {
      "/owner/orders/": { data: { results: [], total: 0 } },
      "/dishes/": {
        data: [
          { id: 11, name: "Soup", slug: "soup", is_published: true, is_available: false, stock_qty: 0, category_name: "Starters" },
          { id: 12, name: "Salad", slug: "salad", is_published: true, is_available: false, stock_qty: 0, category_name: "Starters" },
          { id: 13, name: "Steak", slug: "steak", is_published: true, is_available: true, stock_qty: 5, category_name: "Mains" },
        ],
      },
    };
    wrapper = mountOrders();
    await flushPromises();
    await flushPromises();
    await flushPromises(); // drain the non-blocking seed86Count() fired on mount

    const board = wrapper.findComponent({ name: "OwnerOrders86Board" });
    expect(board.exists()).toBe(true);
    api.post.mockResolvedValueOnce({ data: { restored: 2, stock_cleared: 2, requested: 2 } });
    board.vm.$emit("reset-all");
    await flushPromises();
    // No POST before the owner approves the confirm dialog.
    expect(api.post).not.toHaveBeenCalledWith("/owner/dishes/bulk-reset-availability/", expect.anything());
    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();
    expect(api.post).toHaveBeenCalledWith("/owner/dishes/bulk-reset-availability/", { dish_ids: [11, 12] });
  });

  it("B-04: declining the 86 reset-all dialog posts nothing", async () => {
    _routes = {
      "/owner/orders/": { data: { results: [], total: 0 } },
      "/dishes/": {
        data: [
          { id: 11, name: "Soup", slug: "soup", is_published: true, is_available: false, stock_qty: 0, category_name: "Starters" },
        ],
      },
    };
    wrapper = mountOrders();
    await flushPromises();
    await flushPromises();
    await flushPromises();

    const board = wrapper.findComponent({ name: "OwnerOrders86Board" });
    expect(board.exists()).toBe(true);
    board.vm.$emit("reset-all");
    await flushPromises();
    useConfirmModal()._settle(false);
    await flushPromises();
    expect(api.post).not.toHaveBeenCalled();
  });
});

describe("OwnerOrders — S1-I B-15 wa.me links + B-16 MAD fallback", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // B-15: a national-format order phone ("06…") must link to wa.me/212… —
  // the raw-digits link wa.me/06… is dead. Asserted on the rendered href.
  it("builds wa.me links with the 212 country code for national-format order phones (B-15)", async () => {
    _routes = {
      "/owner/orders/": {
        data: {
          results: [
            order({ id: 1, order_number: "A100", status: "confirmed", customer_phone: "0678901234" }),
            order({ id: 2, order_number: "A101", status: "pending", fulfillment_type: "pickup", customer_name: "Omar", customer_phone: "+212612345678" }),
          ],
          total: 2,
        },
      },
    };

    wrapper = mountOrders();
    await flushPromises();
    await flushPromises(); // drain the non-blocking seed86Count() fired after the order fetch

    const html = wrapper.html();
    expect(html).toContain("https://wa.me/212678901234");
    expect(html).not.toContain("wa.me/0678901234");
    expect(html).toContain("https://wa.me/212612345678");
  });

  // B-16: history-period revenue falls back to MAD (not USD) when history
  // orders carry no currency.
  // NOTE: this file's formatNumber mock returns String(amount) and swallows the
  // currency argument, so the MAD-vs-USD fallback is NOT discriminable through
  // rendered text here — this test guards the revenue path itself
  // (currency-less orders still sum; cancelled orders are excluded). The MAD
  // discrimination for B-16 lives in the OwnerWallet / OwnerShiftClose /
  // OwnerZReport tests, where the real Intl formatter renders the code.
  it("sums history-period revenue for currency-less orders, excluding cancelled ones (B-16)", async () => {
    const { useOrderStore } = await import("../../stores/order");
    useOrderStore().historyOrders = [
      order({ id: 3, order_number: "H1", status: "completed", currency: undefined, total: "137.50" }),
      order({ id: 4, order_number: "H2", status: "cancelled", currency: undefined, total: "50.00" }),
    ];

    wrapper = mountOrders();
    await flushPromises();
    await flushPromises();

    // Open the history tab and set a period (refs, then a tick — the FE-test
    // lesson: never set a ref and immediately click a :disabled-bound button;
    // no click follows here, only a render wait).
    wrapper.vm.activeTab = "history";
    wrapper.vm.historyFrom = "2026-09-01";
    wrapper.vm.historyTo = "2026-09-30";
    await wrapper.vm.$nextTick();
    await flushPromises();

    // Completed 137.50 counts; cancelled 50.00 is excluded from the sum.
    expect(wrapper.text()).toContain("137.5");
    expect(wrapper.text()).not.toContain("187.5");
  });
});
