/**
 * Mount smoke test for OrderStatus.vue (the customer order-tracking page, ~1363 lines).
 *
 * WHY: this is one of the biggest, busiest consumer surfaces and it had NO mount
 * test. The app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, an unguarded browser
 * API) was never caught by a test". OrderStatus is especially exposed: an
 * onMounted that reads localStorage, requests Notification permission, fires the
 * order fetch, opens a realtime channel, adds a visibilitychange listener and
 * schedules a self-rescheduling poll; a 1s countdown setInterval driven by a
 * watch; two status watchers; and ~20 order-derived computeds + template v-fors
 * (timeline / items / money breakdown / ETA ring). Mounting runs all of that for
 * real, so a crash in any of it fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js (the closest analog:
 * poll + countdown + URL-routed api mock + interval cleanup):
 *   - shallowMount (auto-stubs the heavy children: AppIcon, ConnectionDot,
 *     CustomerAuthModal, DeliveryTracker, OrderStatusTimeline, PushPrimingSheet)
 *   - real pinia (customer / order / tenant / toast stores run for real) + a
 *     URL-routed lib/api mock
 *   - useI18n mocked to return deterministic keys
 *   - vue-router mocked (the page imports { useRouter }; it does NOT import
 *     useRoute or RouterLink, so the mock exports only useRouter and <RouterLink>
 *     is covered by a global stub)
 *
 * IDENTIFIER: the page reads the order via a REQUIRED PROP `orderNumber`
 * (defineProps), NOT a route param — fetchStatus() calls
 * api.get(`/order-status/${props.orderNumber}/`). So we mount with
 * props: { orderNumber } and there is no useRoute to mock.
 *
 * useOrderRealtime is MOCKED to a no-op transport: jsdom provides a real
 * `WebSocket`, so leaving it real would open a live ws:// connection at mount and
 * schedule async reconnect timers — nondeterministic console noise / open handles
 * in CI. The WS transport is external I/O (like lib/api), not the page's own setup
 * logic, so mocking it keeps the smoke test deterministic while the page's real
 * setup (destructuring connectionState, wiring the onEvent callback, calling
 * connect/disconnect in the lifecycle hooks) still runs.
 *
 * useReorder / useOrderRating are left REAL: both are setup-safe (they only grab
 * stores and return refs/functions; their network calls fire on user actions, not
 * at mount). The 1s countdown interval + the poll timer are cleared on unmount, so
 * afterEach unmounts to keep timers from leaking between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    // formatCurrency is a LOCAL helper in the page built on formatPrice +
    // currentLocale; these three cover it and every other i18n read.
    formatPrice: (v) => String(v),
    formatDateTime: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires GET /order-status/<n>/, and the various
// actions POST to /orders/<n>/pay-wallet/ etc. Default: everything resolves empty
// ({ data: {} }) — note the page treats a truthy res.data as the loaded order, so
// the default drives the "empty order" main-template render, not a loading/404
// state. Tests set _routes to drive the fully-loaded path.
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

// Realtime channel → no-op transport (see file header). connectionState is a plain
// { value } object: the page reads realtimeState.value and passes it to the
// (stubbed) ConnectionDot, so no reactivity is required.
vi.mock("../../composables/useOrderRealtime", () => ({
  useOrderRealtime: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    connected: { value: false },
    connectionState: { value: "polling" },
  }),
}));

// The page imports { useRouter } from 'vue-router' only (no useRoute, no
// RouterLink import). The factory references no outer const, so no vi.hoisted is
// needed here; <RouterLink> in the template is covered by the global stub below.
vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OrderStatus from "../OrderStatus.vue";

const mountPage = (orderNumber = "A1") =>
  shallowMount(OrderStatus, {
    props: { orderNumber },
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("OrderStatus — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // onMounted reads localStorage (lastOrderNumber / lastOrderAt for the
    // just-placed banner). Clearing keeps that branch (and the push-priming
    // soft-ask) from firing on stale values between tests.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // OrderStatus registers a 1s countdown setInterval (via a watch) + a poll
    // setTimeout, and onUnmounted clears both (and calls orderStore.clearPlacedOrder).
    // Unmounting keeps no timer leaking between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) empty order fetch ({ data: {} }) ──────────────────────────────────
  // The core guard: the async onMounted (localStorage read + fetchStatus + realtime
  // connect + poll schedule) and the whole template must render and not throw.
  // NOTE: res.data === {} is truthy, so the page sets orderData to an empty object
  // and renders its MAIN template (loading flips false once the fetch resolves;
  // notFound stays false) — the degenerate-but-tolerated path that runs every
  // order-derived computed (statusSteps / currentStepIndex / orderSubtotal /
  // showEta …) against {}.
  it("mounts with an empty order fetch without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage("A1");
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header (h1) + items heading always render in the main template — the crash-guard anchors.
    expect(wrapper.text()).toContain("orderStatus.orderNumber");
    expect(wrapper.text()).toContain("orderStatus.items");
  });

  // ── (2) realistic loaded delivery order ───────────────────────────────────
  // Drives the loaded template + timeline + live countdown: a "preparing" delivery
  // order with items, a money breakdown (delivery fee), an ETA (starts the 1s
  // countdown interval), address + payment rows — the own-template paths that only
  // run with a real order payload. status "preparing" (not "ready") deliberately
  // avoids the ready-chime AudioContext path.
  it("mounts a realistic loaded delivery order (timeline + countdown + items) without a crash", async () => {
    _routes = {
      "/order-status/": {
        data: {
          order_number: "A100",
          status: "preparing",
          fulfillment_type: "delivery",
          currency: "MAD",
          total: "75.00",
          items_count: 2,
          delivery_fee: "10.00",
          tip_amount: "0",
          promotion_discount: "0",
          loyalty_discount: "0",
          vat_amount: "0",
          delivery_address: "12 Rue Test, Casablanca",
          payment_status: "paid",
          estimated_ready_minutes: 20,
          estimated_ready_at: new Date(Date.now() + 20 * 60_000).toISOString(),
          created_at: new Date(Date.now() - 5 * 60_000).toISOString(),
          status_updated_at: new Date(Date.now() - 60_000).toISOString(),
          points_earned: 0,
          items: [
            { dish_name: "Burger", note: "", qty: 2, subtotal: "50.00", options: [] },
            { dish_name: "Fries", note: "extra salt", qty: 1, subtotal: "15.00", options: [{ name: "Large" }] },
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountPage("A100");
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Order number flowed into the header (proves the loaded payload rendered).
    expect(wrapper.text()).toContain("A100");
    // Status pill label (statusLabel("preparing") → this key) — proves the loaded
    // status ran through the label + timeline machinery.
    expect(wrapper.text()).toContain("orderStatus.statusPreparing");
  });
});
