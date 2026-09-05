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
