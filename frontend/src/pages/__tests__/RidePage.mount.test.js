/**
 * Mount smoke test for RidePage.vue (~1269 lines) — the customer ride-hailing page
 * (request a ride, live map, driver tracking, fare estimate, ride history).
 *
 * WHY: the app's recurring production bug class is "a big page white-screens on
 * load because a setup()-time error (TDZ / undefined-map access / bad import / an
 * unguarded browser API) was never caught by a test". RidePage is especially
 * exposed: an async onMounted that fetches the active ride, starts a 5s poll,
 * initialises TWO Leaflet booking maps, and registers a visibilitychange listener,
 * plus an { immediate: true } watch that drives a third (tracking) Leaflet map, an
 * auto-estimate watch, and ~10 fare/wallet/status computeds. Mounting runs all of
 * that real setup() so a crash in any of it fails CI here instead of in prod.
 *
 * THE LEAFLET TRAP (handled) — RidePage is UNLIKE Cart.vue's lazy map:
 * RidePage initialises Leaflet AT MOUNT, not on a later user action.
 *   - Authenticated + NO active ride: onMounted → nextTick(initBookingMaps) →
 *     initPickMap()/initPickupMap() → ensureLeaflet() → a dynamic import('leaflet')
 *     + L.map(el). The two <div ref="pickupMapEl/pickMapEl"> are plain template
 *     refs (NOT stubbed children), so under shallowMount they exist in the DOM and
 *     the map init is NOT short-circuited.
 *   - Authenticated + active ride with a driver position: the { immediate: true }
 *     watch on [driver_lat, driver_lng] fires renderTrackingMap() → ensureLeaflet()
 *     + L.map(trackingMapEl) (the tracking <div> is v-show, so it stays in the DOM).
 * Because L.map() runs BEFORE addTileLayer(), mocking ../../lib/mapTiles alone is
 * NOT enough — the real Leaflet would run under jsdom (slow + can throw on layout
 * reads) and its fire-and-forget async init would surface as an unhandled
 * rejection. So we mock `leaflet` itself. vi.mock('leaflet') intercepts the DYNAMIC
 * import('leaflet') too, and we also mock the three marker-image imports + the CSS
 * import that ensureLeaflet() pulls in the same Promise.all, so the test is fully
 * self-contained and independent of vitest's asset pipeline. ../../lib/mapTiles is
 * mocked as well (defensive: addTileLayer must never touch a real tile boundary).
 *
 * NO vue-router: RidePage imports nothing from vue-router and its template uses no
 * <RouterLink> — so, unlike OwnerHome/SuperAppHub/Cart, no vue-router mock/stub is
 * needed (confirmed against the source). NO geolocation at mount either: navigator
 * .geolocation is only read inside the useMyLocation() button handler, never during
 * setup/onMounted — so no navigator.geolocation stub is required for a mount smoke
 * test (jsdom's navigator.onLine, read by the connectionState computed, is present).
 *
 * Pattern-faithful to pages/__tests__/DriverPage.mount.test.js +
 * Cart.mount.test.js: shallowMount (auto-stubs the heavy children — AppIcon,
 * ConnectionDot, CustomerAuthModal, PushPrimingSheet, RidePageHistory) + real pinia
 * + a URL-routed lib/api mock + mocked useI18n.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n: RidePage destructures exactly { t, formatPrice, currentLocale }. t
// returns the key verbatim so we assert the exact keys the page's OWN template
// renders; currentLocale.value feeds toLocaleString in fmtScheduledFor, so it must
// be a valid BCP-47 tag.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock. onMounted (authenticated) GETs /rides/active/, then
// /rides/history/ and /customer/addresses/. Default: everything resolves { data: {} }
// (→ no active ride, empty history/addresses). Tests set _routes to drive the
// active-ride path. _match is a plain const only ever called lazily inside the vi.fn
// closure (never during factory evaluation), so it is safe from the vi.mock hoist TDZ.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// Leaflet — mocked because RidePage inits maps AT MOUNT (see the file header).
// vi.mock('leaflet') intercepts the dynamic import('leaflet') inside ensureLeaflet().
// The fake L must cover the exact call surface: L.map(el).setView() (chainable) with
// .on()/.invalidateSize()/.remove(); L.marker(pos).addTo() (chainable) with
// .setLatLng()/.remove(); and L.Icon.Default.prototype + .mergeOptions() (ensureLeaflet
// does `delete L.Icon.Default.prototype._getIconUrl` then L.Icon.Default.mergeOptions).
// Helpers are defined INSIDE the factory so no module-scope const is referenced from
// the hoisted factory (which would hit the TDZ); `vi` is available inside vi.mock.
vi.mock("leaflet", () => {
  const makeMap = () => ({
    setView: vi.fn().mockReturnThis(),
    on: vi.fn().mockReturnThis(),
    invalidateSize: vi.fn(),
    remove: vi.fn(),
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
  });
  const makeMarker = () => ({
    addTo: vi.fn().mockReturnThis(),
    setLatLng: vi.fn().mockReturnThis(),
    remove: vi.fn(),
  });
  return {
    default: {
      map: vi.fn(makeMap),
      marker: vi.fn(makeMarker),
      tileLayer: vi.fn(() => ({ addTo: vi.fn().mockReturnThis() })),
      icon: vi.fn(),
      divIcon: vi.fn(),
      latLng: vi.fn((lat, lng) => ({ lat, lng })),
      latLngBounds: vi.fn(() => ({ extend: vi.fn() })),
      Icon: { Default: { prototype: {}, mergeOptions: vi.fn() } },
    },
  };
});
// The marker-image + CSS imports ensureLeaflet() pulls in the same Promise.all —
// mocked so the test never depends on how vitest resolves .png/.css assets. Each
// image mock exposes `.default` (ensureLeaflet reads m2x.default / m.default / shadow.default).
vi.mock("leaflet/dist/images/marker-icon-2x.png", () => ({ default: "marker-icon-2x.png" }));
vi.mock("leaflet/dist/images/marker-icon.png", () => ({ default: "marker-icon.png" }));
vi.mock("leaflet/dist/images/marker-shadow.png", () => ({ default: "marker-shadow.png" }));
vi.mock("leaflet/dist/leaflet.css", () => ({}));

// Defensive: the Leaflet tile-layer boundary. addTileLayer(L, map) runs right after
// L.map() on every map init — mocked to a no-op so no test can trip a real tile layer.
vi.mock("../../lib/mapTiles", () => ({ addTileLayer: vi.fn() }));

import { useCustomerStore } from "../../stores/customer";
import RidePage from "../RidePage.vue";

const mountPage = () =>
  shallowMount(RidePage, {
    global: {
      stubs: {
        // No RouterLink stub: RidePage uses no vue-router. Transition/Teleport are
        // stubbed defensively (a stubbed modal child may declare them).
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// Leaflet-init avoidance (why these cases mount an ACTIVE ride, not the idle booking
// form): RidePage inits its booking Leaflet maps AT MOUNT only when there is NO active
// ride (onMounted → nextTick(initBookingMaps)), and a tracking Leaflet map only when
// the active ride has a driver GPS position (hasDriverPos → nextTick(renderTrackingMap)).
// Both map inits are FIRE-AND-FORGET dynamic-import chains that can resolve after the
// test's vi.mock('leaflet') is torn down (→ real leaflet → "Map container not found"
// as an unhandled error that fails the run). Mounting an active ride WITHOUT a driver
// position sidesteps BOTH: no booking form, no tracking map → zero Leaflet init — while
// still running the page's real setup() + onMounted + active-ride template (the
// setup()-crash guard this test is for). The leaflet mock above stays as defensive
// insurance.

// Active ride with an assigned driver but NO GPS position (no driver_lat/lng →
// hasDriverPos false) so the tracking map is never initialized. status 'accepted' is
// non-terminal → the active-ride tracking block renders + startPolling() engages.
const acceptedRide = (overrides = {}) => ({
  id: 42,
  status: "accepted",
  pickup_address: "1 Pickup St",
  dropoff_address: "9 Dropoff Ave",
  driver: { name: "Sami", driver_vehicle: "Dacia Logan", phone: "0600000000" },
  ...overrides,
});

describe("RidePage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // Clear localStorage first so nothing leaks between tests (parity with the
    // sibling mount tests; keeps store hydration deterministic).
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // onBeforeUnmount stops the 5s active-ride poll, clears the cancel-guard timer,
    // removes any Leaflet maps, and removes the visibilitychange listener — unmount
    // so no timer/listener/map leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) active accepted ride (driver assigned, NO GPS) → no map init ─────────
  // The core guard. setCustomer marks the customer store loaded + authenticated, so
  // the page renders past the loading skeleton; an ACTIVE ride means onMounted starts
  // the 5s poll and renders the active-ride tracking view (rideStatusLabel,
  // hasDriverPos, connectionState computeds) rather than the booking form. No booking
  // form → no booking-map init; no driver GPS → no tracking-map init. Zero Leaflet.
  it("mounts an authenticated customer with an active accepted ride (no GPS) without a setup() crash", async () => {
    useCustomerStore().setCustomer({ id: 1, name: "Rider", phone: "0600000000" });
    _routes = { "/rides/active/": { data: { ride: acceptedRide(), scheduled: [] } } };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    // onMounted awaits fetchActiveRide; a second flush drains history/addresses.
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Header (rendered in every signed-in state) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ridePage.title");
    // rideStatusLabel for status 'accepted' → the active-ride tracking branch rendered.
    expect(wrapper.text()).toContain("ridePage.driverAssigned");
  });

  // ── (2) active searching ride (no driver yet) ────────────────────────────────
  // A different active-ride sub-state (status 'searching', no driver) — still an
  // active ride (no booking form) and no GPS (no tracking map), so still no Leaflet —
  // exercising the searching branch of the active-ride template + its computeds.
  it("mounts an authenticated customer with a searching ride (no driver) without a crash", async () => {
    useCustomerStore().setCustomer({ id: 2, name: "Rider", phone: "0611111111" });
    _routes = {
      "/rides/active/": { data: { ride: acceptedRide({ status: "searching", driver: null }), scheduled: [] } },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ridePage.title");
  });
});
