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
// { value } object: the page reads realtimeState.value (poll cadence + the stubbed
// ConnectionDot). It's hoisted so a test can flip it to "live" BEFORE mounting, and
// the page's onEvent callback is captured so a test can simulate a WS "status" push.
const realtime = vi.hoisted(() => ({ state: { value: "polling" }, onEvent: null }));
vi.mock("../../composables/useOrderRealtime", () => ({
  useOrderRealtime: (_getOrderNumber, onEvent) => {
    realtime.onEvent = onEvent;
    return {
      connect: vi.fn(),
      disconnect: vi.fn(),
      connected: { value: false },
      connectionState: realtime.state,
    };
  },
}));

// The page imports { useRouter } from 'vue-router' only (no useRoute, no
// RouterLink import). The factory references no outer const, so no vi.hoisted is
// needed here; <RouterLink> in the template is covered by the global stub below.
vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import api from "../../lib/api";
import CustomerAuthModal from "../../components/CustomerAuthModal.vue";
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
    realtime.state.value = "polling";
    realtime.onEvent = null;
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
    // Header (h1) always renders in the main template — the crash-guard anchor.
    expect(wrapper.text()).toContain("orderStatus.orderNumber");
    // An empty body has no `items` array — the same shape as the server's status-only
    // payload for a non-owner — so it renders the sign-in card, not an empty receipt.
    expect(wrapper.text()).toContain("orderStatus.restrictedTitle");
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

// ── Behaviour: order-status / customer-account fixes ─────────────────────────
const iso = (offsetMin) => new Date(Date.now() + offsetMin * 60_000).toISOString();

// A full (owner) payload; override per test.
const ownerOrder = (overrides = {}) => ({
  order_number: "B1",
  status: "preparing",
  fulfillment_type: "pickup",
  currency: "MAD",
  total: "50.00",
  items_count: 1,
  delivery_fee: "0",
  tip_amount: "0",
  promotion_discount: "0",
  loyalty_discount: "0",
  vat_amount: "0",
  wallet_amount_paid: "0",
  payment_status: "unpaid",
  requires_prepayment: true,
  created_at: iso(-5),
  status_updated_at: iso(-1),
  points_earned: 0,
  receipt_message: "",
  items: [{ dish_slug: "pizza", dish_name: "Pizza", note: "", qty: 1, subtotal: "50.00", options: [] }],
  ...overrides,
});

const statusFetches = () =>
  api.get.mock.calls.filter(([url]) => String(url).includes("/order-status/")).length;

describe("OrderStatus — restricted (status-only) payload (M10)", () => {
  let wrapper;
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    realtime.state.value = "polling";
    vi.clearAllMocks();
    // Exactly what CustomerOrderStatusView returns to a non-owner (e.g. the customer
    // themself, signed out, arriving from Find-my-order): no items / total / payment.
    _routes = {
      "/order-status/": {
        data: {
          order_number: "R1",
          status: "preparing",
          fulfillment_type: "delivery",
          requires_prepayment: true,
          estimated_ready_minutes: 20,
          created_at: iso(-5),
          status_updated_at: iso(-1),
          receipt_message: "",
          tenant_phone: "",
        },
      },
    };
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  it("shows a sign-in card instead of a fake total, empty items and a 'Payment due' pill", async () => {
    wrapper = mountPage("R1");
    await flushPromises();

    const text = wrapper.text();
    expect(wrapper.find("[data-test='restricted-details']").exists()).toBe(true);
    expect(text).toContain("orderStatus.restrictedTitle");
    // Status + progress the minimal payload DOES carry are kept.
    expect(text).toContain("orderStatus.statusPreparing");
    // Misleading owner-only sections are gone: header total/item count + items panel
    // (both read orderStatus.items), the payment pill, the total row.
    expect(text).not.toContain("orderStatus.items");
    expect(text).not.toContain("orderStatus.paymentDue");
    expect(text).not.toContain("orderStatus.total");
  });

  it("signing in from the card reloads the order (and doesn't try to claim it)", async () => {
    wrapper = mountPage("R1");
    await flushPromises();
    expect(statusFetches()).toBe(1);

    await wrapper.find("[data-test='restricted-details'] button").trigger("click");
    wrapper.findComponent(CustomerAuthModal).vm.$emit("authenticated", { id: 42 });
    await flushPromises();

    expect(statusFetches()).toBe(2);
    expect(api.post).not.toHaveBeenCalledWith("/customer/orders/claim/", expect.anything());
  });

  it("a full owner payload still renders the receipt, not the sign-in card", async () => {
    _routes = { "/order-status/": { data: ownerOrder() } };
    wrapper = mountPage("B1");
    await flushPromises();
    expect(wrapper.find("[data-test='restricted-details']").exists()).toBe(false);
    expect(wrapper.text()).toContain("orderStatus.items");
  });
});

describe("OrderStatus — poll cadence while a driver is on the job (M4)", () => {
  let wrapper;
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    // Fake only the timers the page uses; flushPromises (setImmediate) stays real.
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
    realtime.state.value = "live"; // healthy socket
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    realtime.state.value = "polling";
    vi.useRealTimers();
  });

  const deliveryOrder = (delivery) =>
    ownerOrder({ status: "out_for_delivery", fulfillment_type: "delivery", delivery });

  it("polls every 10s with a live socket while the driver is en route (driver events aren't pushed)", async () => {
    _routes = { "/order-status/": { data: deliveryOrder({ status: "picked_up", driver: { name: "Ali" } }) } };
    wrapper = mountPage("D1");
    await flushPromises();
    expect(statusFetches()).toBe(1);

    await vi.advanceTimersByTimeAsync(10_000);
    expect(statusFetches()).toBe(2);
    expect(wrapper.text()).toContain('orderStatus.autoRefresh({"seconds":10})');
  });

  it("also polls fast while still searching for a driver", async () => {
    _routes = { "/order-status/": { data: deliveryOrder({ status: "searching", driver: null }) } };
    wrapper = mountPage("D2");
    await flushPromises();

    await vi.advanceTimersByTimeAsync(10_000);
    expect(statusFetches()).toBe(2);
  });

  it("keeps the 60s safety net on a live socket when no driver is on the job", async () => {
    _routes = { "/order-status/": { data: ownerOrder({ status: "preparing" }) } };
    wrapper = mountPage("P1");
    await flushPromises();

    await vi.advanceTimersByTimeAsync(15_000);
    expect(statusFetches()).toBe(1);
    await vi.advanceTimersByTimeAsync(45_000);
    expect(statusFetches()).toBe(2);
  });

  it("stops the fast poll once the job is delivered", async () => {
    _routes = { "/order-status/": { data: deliveryOrder({ status: "delivered", driver: { name: "Ali" } }) } };
    wrapper = mountPage("D3");
    await flushPromises();

    await vi.advanceTimersByTimeAsync(15_000);
    expect(statusFetches()).toBe(1);
  });
});

describe("OrderStatus — receipt details (L5 / L12 / L13 / M9)", () => {
  let wrapper;
  let warnSpy;
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    realtime.state.value = "polling";
    vi.clearAllMocks();
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    warnSpy.mockRestore();
  });

  const load = async (data) => {
    _routes = { "/order-status/": { data } };
    wrapper = mountPage(data.order_number);
    await flushPromises();
    return wrapper.text();
  };

  it("L5: wallet credits use the order's own currency, not the converting display formatter", async () => {
    const text = await load(ownerOrder({ wallet_amount_paid: "10.00" }));
    const native = new Intl.NumberFormat("en", { style: "currency", currency: "MAD", maximumFractionDigits: 2 }).format(10);
    expect(text).toContain(`orderStatus.walletPaid(${JSON.stringify({ amount: native })})`);
  });

  it("L12: the thank-you note shows while preparing / out for delivery, not when cancelled", async () => {
    expect(await load(ownerOrder({ status: "preparing", receipt_message: "Thanks!" }))).toContain("Thanks!");
    wrapper.unmount();
    expect(await load(ownerOrder({ status: "out_for_delivery", fulfillment_type: "delivery", receipt_message: "Thanks!" }))).toContain("Thanks!");
    wrapper.unmount();
    expect(await load(ownerOrder({ status: "cancelled", receipt_message: "Thanks!" }))).not.toContain("Thanks!");
    wrapper.unmount();
    expect(await load(ownerOrder({ status: "pending", receipt_message: "Thanks!" }))).not.toContain("Thanks!");
  });

  it("L13: two lines of the same dish (different options) keep distinct keys across a refresh", async () => {
    const pizza = (opt) => ({ dish_slug: "pizza", dish_name: "Pizza", note: "", qty: 1, subtotal: "50.00", options: [{ name: opt }] });
    const fries = { dish_slug: "fries", dish_name: "Fries", note: "", qty: 1, subtotal: "15.00", options: [] };
    await load(ownerOrder({ items: [fries, pizza("Large"), pizza("Small")] }));

    // A WS push re-fetches with the lines reordered — Vue's keyed diff runs and would
    // warn "Duplicate keys" under the old dish_name + note key.
    _routes = { "/order-status/": { data: ownerOrder({ items: [pizza("Large"), pizza("Small"), fries] }) } };
    realtime.onEvent("status");
    await flushPromises();

    const dupWarnings = warnSpy.mock.calls.filter((args) => String(args[0]).includes("Duplicate keys"));
    expect(dupWarnings).toEqual([]);
    expect(wrapper.text()).toContain("Large");
    expect(wrapper.text()).toContain("Small");
  });

  it("M9: points read as already credited (reversible) while in progress", async () => {
    const text = await load(ownerOrder({ status: "preparing", points_earned: 12 }));
    expect(wrapper.find("[data-test='points-earned']").exists()).toBe(true);
    expect(text).toContain("+12");
    expect(text).toContain("orderStatus.pointsCreditedHint");
    expect(text).not.toContain("orderStatus.pointsPending");
  });

  it("M9: a cancelled order never shows '+N points'", async () => {
    const text = await load(ownerOrder({ status: "cancelled", points_earned: 12 }));
    expect(wrapper.find("[data-test='points-earned']").exists()).toBe(false);
    expect(text).not.toContain("+12");
  });

  it("a too-late cancel refusal (409 not_cancellable) re-fetches so the button can disappear", async () => {
    await load(ownerOrder({ status: "confirmed", can_cancel: true }));
    expect(statusFetches()).toBe(1);
    api.post.mockImplementationOnce(() =>
      Promise.reject({ response: { status: 409, data: { code: "not_cancellable" } } }),
    );

    const button = (key) => wrapper.findAll("button").find((b) => b.text().includes(key));
    await button("orderStatus.cancelOrder").trigger("click");
    await button("orderStatus.cancelConfirmYes").trigger("click");
    await flushPromises();

    expect(statusFetches()).toBe(2);
  });
});
