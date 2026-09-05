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

// SendPackagePage inits Leaflet AT MOUNT via a FIRE-AND-FORGET chain (onMounted →
// nextTick(initPickMap | renderTrackingMap) → async ensureLeaflet's Promise.all of
// dynamic imports → L.map). Drain it to completion HERE, while vi.mock('leaflet') is
// still active. If it's left pending it resolves during the file's teardown when the
// mock is gone — its late `await import('leaflet')` then gets the REAL leaflet, and
// L.map() on a bare jsdom div throws "Map container not found" as an UNHANDLED error
// that fails the whole run (even though every assertion passed). Waiting for the
// mocked L.map to have been called proves the init reached the map step under the
// mock; the trailing flushes drain the rest.
const settle = async () => {
  await flushPromises();
  await vi.waitFor(() => expect(L.map).toHaveBeenCalled());
  await flushPromises();
  await flushPromises();
};

// An active "accepted" package with an assigned courier that has a live
// position — drives the active-tracking template AND the { immediate:true }
// tracking-map watch (hasDriverPos true → nextTick(renderTrackingMap) →
// ensureLeaflet + L.map at mount). Shape mirrors GET /rides/active/'s
// { ride, scheduled } contract; kind must be 'package' or the page ignores it.
const activePackagePayload = {
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
      driver: {
        name: "Youssef",
        phone: "0600000000",
        driver_vehicle: "Motorbike",
        driver_lat: 33.5921,
        driver_lng: -7.6187,
      },
    },
    scheduled: [],
  },
};

describe("SendPackagePage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(async () => {
    // Drain any still-pending fire-and-forget map init before unmount/teardown, so it
    // resolves under the leaflet mock rather than after it (see settle()).
    await flushPromises();
    // onBeforeUnmount clears the 5s poll interval, the cancel-guard / share-toast
    // timers, both Leaflet maps, and the visibilitychange listener — unmount so
    // none leak between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) authenticated, idle (no active package) — the high-value guard ──────
  // The core case: an authenticated visitor with nothing in flight renders the
  // booking form, whose onMounted schedules initPickMap() → ensureLeaflet() →
  // L.map() AT MOUNT. This is the exact "lazy Leaflet import + map init at
  // setup()" path that white-screens in prod if any import/API is undefined.
  it("mounts an authenticated, idle sender (booking form + pick-map init) without a setup() crash", async () => {
    // setCustomer marks the store loaded + authenticated, so onMounted's auth
    // gate passes and the fetchActiveTrip/history/addresses + initPickMap path
    // runs (mirrors SuperAppHub / DriverPage).
    useCustomerStore().setCustomer({ id: 1, name: "Sara", phone: "0600000000" });
    // _routes empty → /rides/active/ resolves { data: {} } → no active package →
    // booking-form branch → nextTick(initPickMap).

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    // Drain the async onMounted + the fire-and-forget initPickMap → ensureLeaflet →
    // L.map chain to completion under the leaflet mock (see settle()).
    await settle();

    expect(wrapper.exists()).toBe(true);
    // Signed-in header (own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("sendPackage.title");
    // Booking-form-only sections → confirms the signed-in idle form rendered
    // (not the loading / not-signed-in branches).
    expect(wrapper.text()).toContain("ridePage.pickupLabel");
    expect(wrapper.text()).toContain("sendPackage.recipientLabel");
    // Past the auth gate → the not-signed-in prompt is absent.
    expect(wrapper.text()).not.toContain("sendPackage.signInFirst");
    // initPickMap actually reached L.map() — the mount-time Leaflet init ran.
    expect(L.map).toHaveBeenCalled();
  });

  // ── (2) authenticated with an ACTIVE package (accepted + courier w/ GPS) ────
  // Drives the active-tracking template (packageStatusLabel, handover code,
  // share link, cancel guard) AND the { immediate:true } driver-position watch,
  // which — once fetchActiveTrip lands a package with driver_lat/lng — fires
  // nextTick(renderTrackingMap) → ensureLeaflet + L.map for the tracking map at
  // mount. startPolling() also engages (5s interval, cleared on unmount).
  it("mounts an authenticated sender with an active tracked package (tracking-map init) without a crash", async () => {
    useCustomerStore().setCustomer({ id: 2, name: "Omar", phone: "0611111111" });
    _routes = { "/rides/active/": activePackagePayload };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    // Drain onMounted's fetchActiveTrip → activePackage set → tracking-map watch →
    // nextTick(renderTrackingMap) → ensureLeaflet → L.map, to completion under the
    // leaflet mock (see settle()).
    await settle();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("sendPackage.title");
    // Loaded assertion: packageStatusLabel for 'accepted' → courierAssigned key,
    // and the fetched pickup address both render in the active-tracking banner.
    expect(wrapper.text()).toContain("sendPackage.courierAssigned");
    expect(wrapper.text()).toContain("1 Pickup St");
    // The tracking map's mount-time Leaflet init actually ran (renderTrackingMap
    // reached L.map without throwing on the way).
    expect(L.map).toHaveBeenCalled();
  });
});
