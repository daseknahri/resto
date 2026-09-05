/**
 * Mount smoke test for OwnerKitchen.vue (the Kitchen Display System / KDS, ~1333 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load because a
 * setup()-time error (TDZ, an undefined-map access, an unguarded browser API) was never caught
 * by a test". OwnerKitchen is heavily exposed: a `<script setup>` with ~740 lines of refs /
 * computeds / helpers, a localStorage-backed auto-print + sound preference read AT setup, a
 * `useWakeLock()` call, a `useOwnerRealtime(cb)` live-WebSocket registration, a `usePrintTicket()`
 * / `useConfirmModal()` / `useNowTicker()` chain, an async onMounted (setFlushCallbacks →
 * setupConnectivityListeners → fullscreenchange + visibilitychange listeners → waiter.fetchOrders
 * → seed the seen-order set), a KeepAlive live-loop (clock + 10s poll + WS connect) behind
 * onActivated, a dozen order-derived computeds (activeOrders / stationFilters / prepStationFilters
 * / allDayItems + their fallback watchers) and a stubbed OwnerKitchenOrderCard v-for. Mounting
 * runs all of that for real, so a crash in any of it fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerOrders.mount.test.js (the closest analog — an owner
 * board that mocks a live WebSocket, has a lazy AudioContext new-order chime, polls on an
 * interval and reads a store): shallowMount (auto-stubs the heavy children — BusyModeControl,
 * OwnerKitchenFilterBars, OwnerKitchenNewOrderBanner, OwnerKitchen86Board, OwnerKitchenOrderCard),
 * real pinia (the waiter / toast stores run for real), a URL-routed lib/api mock, and mocked
 * useI18n + useOwnerRealtime.
 *
 * Left REAL (jsdom-safe): useNowTicker (30s ticker — its interval starts in onMounted, so it DOES
 * run under a bare mount; unmount clears it), useWakeLock (feature-detects `"wakeLock" in
 * navigator`, false in jsdom → every acquire() short-circuits, so no wakeLock call), usePrintTicket
 * (a pure factory — only touches the DOM when a print button is clicked), useConfirmModal (pure),
 * and the waiter / toast stores. waiter.fetchOrders() hits GET /staff/orders/ and tolerates an
 * empty `{ data: {} }` (reads `res.data?.results` → []), so the fresh-kitchen path renders.
 *
 * Mocked (a NETWORK/ENV boundary, exactly like lib/api): useOwnerRealtime. The page registers a
 * kitchen-local WS (`useOwnerRealtime(cb)`) and, on activation, calls connect(); the real
 * composable opens a live WebSocket to `wss://<host>/ws/owner/` and schedules reconnect timers.
 * The stub keeps the page's OWN realtime wiring exercised: the `useOwnerRealtime(cb)` call, the
 * `computed(() => kitchenRealtime.connectionState?.value ?? "connecting")` read (→ the live/polling
 * top-bar chip), and the onUnmounted disconnect(). Its return shape mirrors the real
 * useRealtimeChannel: `{ connect, disconnect, connected, connectionState }` (connectionState a ref).
 *
 * NOT stubbed (verified from source, noted for the next reader):
 *   - AudioContext — created LAZILY inside _ensureAudioCtx(), called only from toggleKitchenSound
 *     (a user click on the sound toggle) or playAlert (the new-order chime). playAlert only fires
 *     from checkNewOrders(), reached via doPoll() — and doPoll() runs in onActivated / the poll
 *     interval / a visibilitychange, none of which fire under a bare mount. So NO AudioContext is
 *     constructed at mount. (jsdom has none anyway, and _ensureAudioCtx + playAlert are try/caught.)
 *   - The clock + 10s poll + WS connect live-loop is gated behind onActivated, which ONLY fires
 *     under a <KeepAlive> host (this is a bare mount) — so those intervals never start here. The
 *     setup() body + the async onMounted (the actual white-screen surface) run fully; onUnmounted
 *     still runs on unmount and clears the useNowTicker interval + removes the window/document
 *     listeners registered in onMounted.
 *   - Fullscreen / navigator.vibrate — only touched in click handlers or the fullscreenchange
 *     handler, never at mount (onUnmounted's exitFullscreen is guarded on document.fullscreenElement,
 *     null in jsdom).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in OwnerKitchen is { t, formatDateTime, currentLocale } — the mock MUST
// return all three or setup throws on the destructure.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k) => k, // key verbatim → assertions read the raw key
    formatDateTime: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: onMounted fires a GET (/staff/orders/ via the waiter store). Default:
// everything resolves empty so the fresh-kitchen path renders. Tests set _routes to drive the
// loaded path. (_match is referenced only from inside the lazy vi.fn closures below, never from a
// hoisted factory, so no TDZ.)
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

// useOwnerRealtime is a network boundary (a live WebSocket). Stub it so connect()/disconnect() are
// no-ops and connectionState is inert. The page reads `connectionState?.value` in a computed, so
// the stub must expose a `.value`. Shape mirrors the real useRealtimeChannel return.
vi.mock("../../composables/useOwnerRealtime", () => ({
  useOwnerRealtime: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    connected: { value: false },
    connectionState: { value: "polling" },
  }),
}));

import OwnerKitchen from "../OwnerKitchen.vue";
// Imported ONLY to count rendered order tickets via findAllComponents — it stays stubbed by
// shallowMount (its setup never runs), so the import is a benign module eval (it only imports
// `computed` + the already-mocked useI18n). Order-number text lives inside this child's template,
// so with the card stubbed the loaded assertion counts stub instances, not order-number text.
import OwnerKitchenOrderCard from "../../components/OwnerKitchenOrderCard.vue";

const mountKitchen = () => shallowMount(OwnerKitchen);

// A minimal-but-realistic active kitchen ticket carrying exactly the fields the board's computeds
// read: status (ACTIVE_STATUSES gate + stationFilters), fulfillment_type (station filter),
// table_label / order_number / customer_name (search), and items with station / is_voided / qty /
// course / is_ready (prepStationFilters + allDayItems + the fired-course helpers). Deliberately
// keeps delivery_job null and fired_course sane so the row stays on its simple path.
const ticket = (overrides = {}) => ({
  id: 1,
  order_number: "K100",
  status: "preparing",
  fulfillment_type: "table",
  table_label: "T3",
  customer_name: "Sara",
  created_at: new Date().toISOString(),
  scheduled_for: null,
  fired_course: 1,
  delivery_job: null,
  items: [
    { id: 11, dish_name: "Cheeseburger", qty: 2, course: 0, station: "grill", is_ready: false, is_voided: false },
    { id: 12, dish_name: "Fries", qty: 1, course: 0, station: "fry", is_ready: false, is_voided: false },
  ],
  ...overrides,
});

describe("OwnerKitchen — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // The auto-print + sound preferences read localStorage at setup (kepoli.kitchen.autoPrint,
    // kitchen:sound). Clear it first so no stale value bleeds between tests.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // onMounted starts the useNowTicker 30s interval and adds window online/offline + document
    // fullscreenchange/visibilitychange listeners; unmount runs onUnmounted → clearInterval +
    // removeEventListener + realtime.disconnect() so no timer/listener leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) empty queue: no active orders ─────────────────────────────────────
  // The core guard: the whole `<script setup>` + the async onMounted (fetchOrders + seed the
  // seen-order set) + the full template must render with empty data and NOT throw.
  it("mounts an empty kitchen board (no orders) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountKitchen();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Top-bar kicker (always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("kitchen.title");
    // Empty orders → the "All clear" empty state renders.
    expect(wrapper.text()).toContain("kitchen.allClear");
  });

  // ── (2) loaded queue with active tickets ──────────────────────────────────
  // Drives the order-derived computeds + the card v-for (activeOrders / allActiveOrders /
  // stationFilters / prepStationFilters + their fallback watchers) — the own-template paths that
  // only run with a non-empty orders array.
  it("mounts a loaded board with active tickets without a crash", async () => {
    _routes = {
      "/staff/orders/": {
        data: {
          results: [
            ticket({ id: 1, order_number: "K100", status: "preparing", fulfillment_type: "table" }),
            ticket({ id: 2, order_number: "K101", status: "pending", fulfillment_type: "pickup", table_label: "", customer_name: "Omar" }),
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountKitchen();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("kitchen.title");
    // Two active tickets → the order grid renders two OwnerKitchenOrderCard instances (stubbed).
    // Their presence proves activeOrders (the ACTIVE_STATUSES filter) + the v-for ran with data.
    expect(wrapper.findAllComponents(OwnerKitchenOrderCard)).toHaveLength(2);
    // The "All clear" empty state must be gone now that the board has active tickets.
    expect(wrapper.text()).not.toContain("kitchen.allClear");
  });
});
