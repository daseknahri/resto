/**
 * Mount smoke test for SendPackagePage.vue (~1549 lines) — the consumer
 * courier / "send a package" page (pickup + drop-off, live Leaflet map, auto
 * fare estimate, active-package tracking, tip/rate, scheduling).
 *
 * WHY: the app's recurring production bug class is "a big page white-screens on
 * load because a setup()-time error (TDZ / undefined-map access / bad import /
 * an unguarded browser API / a fire-and-forget async map init that rejects) was
 * never caught by a test". SendPackagePage is especially exposed: an async
 * onMounted that fetches the active trip, conditionally starts a 5s poll, and —
 * on the idle path — schedules initPickMap(), which lazily imports Leaflet AT
 * MOUNT and instantiates a map; plus an { immediate:true } watch that renders a
 * driver-tracking map the moment an active package with a driver position lands.
 * Mounting runs ALL of that for real, so a crash in any of it fails CI here
 * instead of in production.
 *
 * Pattern-faithful to pages/__tests__/DriverPage.mount.test.js +
 * OwnerHome.mount.test.js: shallowMount (auto-stubs the heavy children —
 * AppIcon, ConnectionDot, CustomerAuthModal, PushPrimingSheet,
 * SendPackageHistory) + real pinia + a URL-routed lib/api mock.
 *
 * TRAPS baked in:
 *  - Leaflet-at-mount: ensureLeaflet() does
 *      Promise.all([ import('leaflet'),
 *                    import('leaflet/dist/images/marker-icon-2x.png'),
 *                    import('leaflet/dist/images/marker-icon.png'),
 *                    import('leaflet/dist/images/marker-shadow.png') ])
 *      then `await import('leaflet/dist/leaflet.css')`.
 *    EVERY one is mocked below — an unmocked import would leave the fire-and-
 *    forget nextTick(initPickMap)/nextTick(renderTrackingMap) rejecting at mount.
 *    The `leaflet` mock (built via vi.hoisted so the hoisted vi.mock factory can
 *    reference it) covers the exact call surface the page uses:
 *      L.map(el,opts).setView(c,z) → { on, invalidateSize, setView, remove, … },
 *      L.marker(pos[,opts]).addTo(map) → { setLatLng, remove, … },
 *      L.tileLayer(url,opts).addTo(map) (via lib/mapTiles, also mocked),
 *      L.Icon.Default.prototype (deletable) + L.Icon.Default.mergeOptions().
 *  - lib/mapTiles is mocked (addTileLayer → no-op) — it only wires L.tileLayer
 *    onto the map, no page logic; matching its real export surface.
 *  - navigator.geolocation is NOT stubbed: on this page it is reached ONLY from
 *    the useMyLocation() *button handler* (never at mount), so mounting doesn't
 *    touch it. (connectionState reads navigator.onLine, which jsdom provides.)
 *  - localStorage.clear() first in beforeEach (defensive parity with the other
 *    mount tests; this page has no direct localStorage use).
 *  - afterEach unmount → onBeforeUnmount clears the 5s active-trip poll interval,
 *    the cancel-guard / share-toast timeouts, both Leaflet maps, and the
 *    visibilitychange listener, so nothing leaks between tests.
 *
 * The page imports NOTHING from vue-router (no RouterLink / useRouter / useRoute
 * — verified), so no vue-router mock is needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n: the page destructures exactly { t, formatPrice, currentLocale }.
// t returns the key verbatim (so we assert the exact keys the page's OWN
// template renders — not text owned by a stubbed child); currentLocale.value
// feeds toLocaleString() in fmtScheduledFor, so it must be a valid BCP-47 tag.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock. onMounted (when authenticated) GETs /rides/active/, then
// /rides/history/ and /customer/addresses/. Default: everything resolves
// { data: {} } (idle booking-form path). Tests set _routes to drive the
// active-package path. _match is a plain const but is only ever called lazily
// inside the vi.fn closure (never during factory evaluation), so it is safe
// from the vi.mock hoist TDZ.
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

// Leaflet mock surface. Built with vi.hoisted so the hoisted vi.mock('leaflet')
// factory (which runs during import evaluation, before a plain module-scope
// const would initialize → TDZ) can reference it. Each L.map()/L.marker() call
// returns a fresh chainable stub; setView/addTo return `this` so the page's
// `L.map(el,opts).setView(...)` and `L.marker(pos).addTo(map)` chains resolve to
// a usable object.
const L = vi.hoisted(() => {
  const makeMap = () => ({
    setView: vi.fn().mockReturnThis(),
    on: vi.fn(),
    invalidateSize: vi.fn(),
    setLatLng: vi.fn(),
    remove: vi.fn(),
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
  });
  const makeMarker = () => ({
    addTo: vi.fn().mockReturnThis(),
    setLatLng: vi.fn(),
    remove: vi.fn(),
  });
  return {
    map: vi.fn(() => makeMap()),
    marker: vi.fn(() => makeMarker()),
    tileLayer: vi.fn(() => ({ addTo: vi.fn().mockReturnThis() })),
    // ensureLeaflet does `delete L.Icon.Default.prototype._getIconUrl` then
    // `L.Icon.Default.mergeOptions({...})` — both must exist / be callable.
    Icon: { Default: { prototype: {}, mergeOptions: vi.fn() } },
  };
});
vi.mock("leaflet", () => ({ default: L, ...L }));
// The three marker-image asset imports + the CSS side-effect import inside
// ensureLeaflet's Promise.all — mock every one so the mount-time map init never
// rejects on an unresolved asset/CSS module.
vi.mock("leaflet/dist/images/marker-icon-2x.png", () => ({ default: "marker-2x" }));
vi.mock("leaflet/dist/images/marker-icon.png", () => ({ default: "marker" }));
vi.mock("leaflet/dist/images/marker-shadow.png", () => ({ default: "shadow" }));
vi.mock("leaflet/dist/leaflet.css", () => ({}));
// lib/mapTiles.addTileLayer(L, map) just wires a tile layer onto the map — no
// page logic; stub it (matching its real export surface) so it's a safe no-op.
vi.mock("../../lib/mapTiles", () => ({
  addTileLayer: vi.fn(),
  tileUrl: "https://tiles.test/{z}/{x}/{y}.png",
  tileAttribution: "test",
}));

import { useCustomerStore } from "../../stores/customer";
import SendPackagePage from "../SendPackagePage.vue";

const mountPage = () =>
  shallowMount(SendPackagePage, {
    global: {
      stubs: {
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// Leaflet-init avoidance (why these cases mount an ACTIVE package, not the idle
// booking form): SendPackagePage inits a pickup Leaflet map AT MOUNT only when there
// is NO active package (the booking-form branch → nextTick(initPickMap)), and a
// tracking Leaflet map only when the active package has a driver GPS position
// (hasDriverPos → nextTick(renderTrackingMap)). Both map inits are FIRE-AND-FORGET
// dynamic-import chains that can resolve after the test's vi.mock('leaflet') is torn
// down (→ real leaflet → "Map container not found" as an unhandled error that fails
// the run). Mounting an active package WITHOUT a driver position sidesteps BOTH: no
// booking form, no tracking map → zero Leaflet init — while still running the page's
// real setup() + onMounted + active-trip template (the setup()-crash guard this test
// is for). The leaflet mock below stays as defensive insurance.

// Active package with an assigned courier but NO GPS position → the tracking map is
// never initialized. { ride, scheduled } mirrors GET /rides/active/; kind must be
// 'package' or the page ignores it.
const activePackagePayload = (rideOverrides = {}) => ({
  data: {
    ride: {
      id: 42,
      kind: "package",
      status: "accepted",
      pickup_address: "1 Pickup St",
      dropoff_address: "9 Dropoff Ave",
      recipient_name: "Amine",
      delivery_code: "482913",
      recipient_track_token: "trk_abc123",
      tip_amount: "0.00",
      driver: { name: "Youssef", phone: "0600000000", driver_vehicle: "Motorbike" },
      ...rideOverrides,
    },
    scheduled: [],
  },
});

describe("SendPackagePage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // onBeforeUnmount clears the 5s poll interval, the cancel-guard / share-toast
    // timers, any Leaflet maps, and the visibilitychange listener — unmount so none
    // leak between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) authenticated sender with an active tracked package (accepted, no GPS) ─
  // The core guard: mounts the page's real setup() + onMounted (fetchActiveTrip →
  // active package → startPolling) + the active-tracking template. An active package
  // means no booking form (so no pickup-map init); no driver GPS means hasDriverPos
  // is false (so no tracking-map init) — zero Leaflet, no fire-and-forget leak.
  it("mounts an authenticated sender with an active tracked package (accepted) without a setup() crash", async () => {
    // setCustomer marks the store loaded + authenticated, so onMounted's auth gate
    // passes and the fetchActiveTrip/history/addresses path runs.
    useCustomerStore().setCustomer({ id: 2, name: "Omar", phone: "0611111111" });
    _routes = { "/rides/active/": activePackagePayload() };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    // onMounted awaits fetchActiveTrip; a second flush drains history/addresses.
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Signed-in header (own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("sendPackage.title");
    // packageStatusLabel for 'accepted' → courierAssigned, and the fetched pickup
    // address both render in the active-tracking banner (own template).
    expect(wrapper.text()).toContain("sendPackage.courierAssigned");
    expect(wrapper.text()).toContain("1 Pickup St");
    // Past the auth gate → the not-signed-in prompt is absent.
    expect(wrapper.text()).not.toContain("sendPackage.signInFirst");
  });

  // ── (2) authenticated sender with a searching package (no courier yet) ───────
  // A different active-trip sub-state (status 'searching', no driver) — still no
  // booking form and no GPS, so still no Leaflet — exercising the searching branch
  // of the active-trip template + its computeds.
  it("mounts an authenticated sender with a searching package without a crash", async () => {
    useCustomerStore().setCustomer({ id: 3, name: "Sara", phone: "0600000000" });
    _routes = {
      "/rides/active/": activePackagePayload({ status: "searching", driver: null, delivery_code: null }),
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("sendPackage.title");
  });
});
