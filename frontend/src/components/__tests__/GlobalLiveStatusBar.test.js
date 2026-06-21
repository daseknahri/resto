/**
 * Unit tests for GlobalLiveStatusBar — the persistent slim status bar that
 * surfaces in-progress orders, rides, and packages across the customer app.
 *
 * Contracts verified:
 *   - hidden when no active items
 *   - shows order bar (with restaurant name) when an active order exists
 *   - shows ride bar when a ride is active and no order is active
 *   - shows package bar when only a package is active
 *   - overflow badge shows "+N more" for multiple concurrent active items
 *   - routes to marketplace-order-status when restaurant_slug is present
 *   - routes to order-status when no restaurant_slug
 *   - hidden when not authenticated (even if activeItems is populated)
 *   - aria-label on the link describes the action
 *   - load() called on mount when authenticated; skipped when not
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import { ref } from "vue";

// ── Mocks ─────────────────────────────────────────────────────────────────

// Deterministic i18n
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (key, params = {}) => {
      const map = {
        "globalLiveStatusBar.ariaRegion":           "Active order/ride status",
        "globalLiveStatusBar.orderLabel":            "Your order",
        "globalLiveStatusBar.orderFromName":         `Order from ${params.name || ""}`,
        "globalLiveStatusBar.rideLabel":             "Your ride",
        "globalLiveStatusBar.packageLabel":          "Your package",
        "globalLiveStatusBar.tapToTrackOrder":       `Track order #${params.number || ""}`,
        "globalLiveStatusBar.tapToTrackRide":        "Track your ride",
        "globalLiveStatusBar.tapToTrackPackage":     "Track your package",
        "globalLiveStatusBar.moreActive":            `+${params.n || 0} more active`,
        "globalLiveStatusBar.statusPending":         "Pending",
        "globalLiveStatusBar.statusConfirmed":       "Confirmed",
        "globalLiveStatusBar.statusPreparing":       "Preparing",
        "globalLiveStatusBar.statusReady":           "Ready",
        "globalLiveStatusBar.statusOutForDelivery":  "On the way",
        "globalLiveStatusBar.statusSearchingDriver": "Finding driver",
        "globalLiveStatusBar.statusDriverOnWay":     "Driver on the way",
        "globalLiveStatusBar.statusDriverArrived":   "Driver arrived",
        "globalLiveStatusBar.statusSearchingCourier":"Finding courier",
        "globalLiveStatusBar.statusCourierOnWay":    "Courier on the way",
        "globalLiveStatusBar.statusCourierArrived":  "Courier at pickup",
        "globalLiveStatusBar.statusPackageInProgress":"In transit",
        "globalLiveStatusBar.statusInProgress":      "In progress",
        "tripSchedule.statusScheduled":              "Scheduled",
      };
      return map[key] ?? key;
    },
  }),
}));

// Controllable activity state
let _activeItems = ref({ orders: [], ride: null, package: null });
let _mockLoad = vi.fn();

vi.mock("../../composables/useCustomerActivity", () => ({
  useCustomerActivity: () => ({
    activeItems: _activeItems,
    load: _mockLoad,
  }),
}));

// Controllable auth state — expose as plain boolean-returning computed proxy
// so that `customerStore.isAuthenticated` in the component reads a value, not a ref.
let _authValue = true;

vi.mock("../../stores/customer", () => ({
  useCustomerStore: () => ({
    get isAuthenticated() { return _authValue; },
  }),
}));

// RouterLink stub — renders an <a>; passes aria-label via inheritAttrs
const RouterLink = {
  name: "RouterLink",
  inheritAttrs: true,
  props: ["to"],
  template: `<a :href="JSON.stringify(to)" v-bind="$attrs"><slot /></a>`,
};

// Transition stub — renders slot directly (no animation in tests)
const Transition = {
  name: "Transition",
  template: `<slot />`,
};

import GlobalLiveStatusBar from "../GlobalLiveStatusBar.vue";

const mountBar = () =>
  mount(GlobalLiveStatusBar, {
    global: {
      stubs: { RouterLink, Transition },
    },
  });

// ── Helpers ───────────────────────────────────────────────────────────────
const setActive = (items) => {
  _activeItems.value = { orders: [], ride: null, package: null, ...items };
};

// ── Tests ─────────────────────────────────────────────────────────────────
describe("GlobalLiveStatusBar", () => {
  beforeEach(() => {
    _mockLoad.mockReset();
    _mockLoad.mockResolvedValue(undefined);
    _authValue = true;
    setActive({});
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("is hidden when no active items exist", () => {
    setActive({});
    const w = mountBar();
    expect(w.find(".glsb-link").exists()).toBe(false);
  });

  it("is hidden when not authenticated even if activeItems is populated", () => {
    _authValue = false;
    setActive({
      orders: [{ order_number: "ORD-001", status: "preparing", restaurant_name: "Foo", restaurant_slug: "foo" }],
    });
    const w = mountBar();
    expect(w.find(".glsb-link").exists()).toBe(false);
  });

  it("shows the bar with restaurant name when an active order exists", async () => {
    setActive({
      orders: [{
        order_number: "ORD-123",
        status: "preparing",
        restaurant_name: "Burger Place",
        restaurant_slug: "burger-place",
      }],
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-link").exists()).toBe(true);
    expect(w.find(".glsb-label").text()).toContain("Burger Place");
    expect(w.find(".glsb-chip").text()).toBe("Preparing");
  });

  it("shows correct status chip for out_for_delivery", async () => {
    setActive({
      orders: [{
        order_number: "ORD-77",
        status: "out_for_delivery",
        restaurant_name: "Pizza Co",
        restaurant_slug: "pizza-co",
      }],
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-label").text()).toContain("Pizza Co");
    expect(w.find(".glsb-chip").text()).toBe("On the way");
  });

  it("routes to marketplace-order-status when restaurant_slug is present", async () => {
    setActive({
      orders: [{
        order_number: "ORD-88",
        status: "confirmed",
        restaurant_name: "Sushi Bar",
        restaurant_slug: "sushi-bar",
      }],
    });
    const w = mountBar();
    await w.vm.$nextTick();
    const href = w.find(".glsb-link").attributes("href") || "";
    const to = JSON.parse(href);
    expect(to.name).toBe("marketplace-order-status");
    expect(to.params.slug).toBe("sushi-bar");
    expect(to.params.orderNumber).toBe("ORD-88");
  });

  it("routes to order-status when no restaurant_slug", async () => {
    setActive({
      orders: [{
        order_number: "ORD-99",
        status: "pending",
        restaurant_name: "",
        restaurant_slug: "",
      }],
    });
    const w = mountBar();
    await w.vm.$nextTick();
    const href = w.find(".glsb-link").attributes("href") || "";
    const to = JSON.parse(href);
    expect(to.name).toBe("order-status");
    expect(to.params.orderNumber).toBe("ORD-99");
  });

  it("shows the ride bar when a ride is active and no orders are active", async () => {
    setActive({
      orders: [],
      ride: { id: 5, status: "accepted", dropoff_address: "123 Main St" },
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-link").exists()).toBe(true);
    expect(w.find(".glsb-label").text()).toContain("123 Main St");
    expect(w.find(".glsb-chip").text()).toBe("Driver on the way");
    const to = JSON.parse(w.find(".glsb-link").attributes("href") || "{}");
    expect(to.name).toBe("ride");
  });

  it("shows the package bar when only a package is active", async () => {
    setActive({
      orders: [],
      ride: null,
      package: { id: 9, status: "in_progress", dropoff_address: "Drop St 7" },
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-label").text()).toContain("Drop St 7");
    expect(w.find(".glsb-chip").text()).toBe("In transit");
    const to = JSON.parse(w.find(".glsb-link").attributes("href") || "{}");
    expect(to.name).toBe("send-package");
  });

  it("shows overflow badge when multiple items are active", async () => {
    setActive({
      orders: [
        { order_number: "A1", status: "preparing", restaurant_name: "R1", restaurant_slug: "r1" },
        { order_number: "A2", status: "pending",   restaurant_name: "R2", restaurant_slug: "r2" },
      ],
      ride: { id: 3, status: "searching", dropoff_address: "Somewhere" },
    });
    const w = mountBar();
    await w.vm.$nextTick();
    const overflow = w.find(".glsb-overflow");
    expect(overflow.exists()).toBe(true);
    // 2 orders + 1 ride = 3 total; primary = 1; overflow = 2
    expect(overflow.text()).toBe("+2");
  });

  it("does NOT show overflow badge when only one item is active", async () => {
    setActive({
      orders: [{ order_number: "X1", status: "confirmed", restaurant_name: "X", restaurant_slug: "x" }],
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-overflow").exists()).toBe(false);
  });

  it("has an aria-label on the link describing the action (order number present)", async () => {
    setActive({
      orders: [{
        order_number: "ORD-555",
        status: "confirmed",
        restaurant_name: "Taco Bell",
        restaurant_slug: "taco-bell",
      }],
    });
    const w = mountBar();
    await w.vm.$nextTick();
    // The aria-label is bound to the <RouterLink> which our stub passes through via v-bind="$attrs"
    const ariaLabel = w.find(".glsb-link").attributes("aria-label") || "";
    expect(ariaLabel).toContain("ORD-555");
  });

  it("calls load() on mount when authenticated", async () => {
    _authValue = true;
    mountBar();
    // Drain the onMounted async load
    await vi.runAllMicrotasksAsync?.() ?? await Promise.resolve();
    await _mockLoad.mock.results[0]?.value;
    expect(_mockLoad).toHaveBeenCalledTimes(1);
  });

  it("does not call load() on mount when not authenticated", async () => {
    _authValue = false;
    mountBar();
    await Promise.resolve();
    expect(_mockLoad).not.toHaveBeenCalled();
  });

  it("uses 'Your order' label when restaurant_name is empty", async () => {
    setActive({
      orders: [{
        order_number: "ORD-ZZ",
        status: "pending",
        restaurant_name: "",
        restaurant_slug: "",
      }],
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-label").text()).toBe("Your order");
  });

  it("falls back to rideLabel when ride has no dropoff_address", async () => {
    setActive({
      ride: { id: 7, status: "searching", dropoff_address: "" },
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-label").text()).toBe("Your ride");
  });

  it("falls back to packageLabel when package has no dropoff_address", async () => {
    setActive({
      package: { id: 11, status: "searching", dropoff_address: "" },
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-label").text()).toBe("Your package");
  });

  it("orders take priority over rides in the primary card", async () => {
    setActive({
      orders: [{ order_number: "PRI-1", status: "preparing", restaurant_name: "Priority", restaurant_slug: "pri" }],
      ride:   { id: 2, status: "accepted", dropoff_address: "Somewhere" },
    });
    const w = mountBar();
    await w.vm.$nextTick();
    expect(w.find(".glsb-label").text()).toContain("Priority");
  });

  it("sets up a 30-second polling interval on mount", async () => {
    _authValue = true;
    mountBar();
    // Drain mount
    await Promise.resolve();
    const callsAfterMount = _mockLoad.mock.calls.length;
    // Advance 30 s — should trigger one more call (force refresh)
    vi.advanceTimersByTime(30_000);
    await Promise.resolve();
    expect(_mockLoad.mock.calls.length).toBeGreaterThan(callsAfterMount);
  });
});
