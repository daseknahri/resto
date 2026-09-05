/**
 * Mount smoke test for DriverPage.vue (~2299 lines) — the delivery-driver page
 * (go online, active job, live GPS tracking, cash-out, rides).
 *
 * WHY: the app's recurring production bug class is "a big page white-screens on
 * load because a setup()-time error (TDZ / undefined-map access / bad import / an
 * unguarded browser API) was never caught by a test". DriverPage is especially
 * exposed: an async onMounted that authenticates, fetches /driver/status/, and —
 * for an ONLINE-shift auto-resume — calls navigator.geolocation.watchPosition(),
 * starts an adaptive job poll interval AND a 1-second offer-countdown interval, and
 * wires a dozen job-derived computeds as props into the sticky active-job hero.
 * Only the extracted CHILD components (DriverPageActiveJob, DriverOfferModal, …)
 * had tests; the PAGE's own setup() had none. Mounting runs all of it for real, so
 * a crash in any of it fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * SuperAppHub.mount.test.js: shallowMount (auto-stubs the heavy children) + real
 * pinia + a URL-routed lib/api mock.
 *
 * TRAPS baked in:
 *  - navigator.geolocation: jsdom has none. startGeo() fires watchPosition at mount
 *    on the online-shift auto-resume path, so we add a geolocation stub to the REAL
 *    navigator BEFORE mount (Object.defineProperty, preserving navigator's other
 *    fields — the page also reads window.navigator.standalone, navigator.wakeLock,
 *    and, at import, navigator.serviceWorker). Without the stub startGeo() would
 *    early-return; with it, the true production watchPosition/clearWatch path runs.
 *  - localStorage.clear() first in beforeEach (the page reads/writes the
 *    welcomed / offer-sound flags there) so a test-1 write can't leak into test 2.
 *  - afterEach unmount → onBeforeUnmount clears the poll + countdown intervals and
 *    the geo watch, so no timer/watch leaks between tests.
 *  - RouterLink/Transition/Teleport stubbed in global.stubs. DriverPage imports
 *    NOTHING from vue-router (no useRouter/useRoute) — only <RouterLink> in its
 *    template — so no vue-router mock is needed, just the RouterLink global stub.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n: DriverPage destructures ONLY { t, currentLocale }. t returns the key
// verbatim (so we assert the exact keys the page's OWN template renders — not text
// owned by a stubbed child); currentLocale.value feeds Intl.NumberFormat inside
// fmtMoney, so it must be a valid BCP-47 tag.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatCurrency: (v) => String(v),
    formatNumber: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock. onMounted → customerStore.fetchCustomer() GETs
// /customer/session/ (short-circuited here via setCustomer()); when authenticated it
// GETs /driver/status/, and for an approved driver bootstrapDriverDashboard() GETs
// /driver/jobs/, /driver/earnings/, /driver/cashout/. Default: everything resolves
// { data: {} } (the guest path). Tests set _routes to drive the approved/online path.
// _match is a plain const but is only ever called lazily inside the vi.fn closure
// (never during factory evaluation), so it is safe from the vi.mock hoist TDZ.
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

import { useCustomerStore } from "../../stores/customer";
import DriverPage from "../DriverPage.vue";

// Geolocation stub — added to the REAL navigator so startGeo()'s
// `'geolocation' in navigator` guard passes and watchPosition actually runs for the
// online-shift auto-resume (and clearWatch runs on unmount).
const geoStub = {
  watchPosition: vi.fn(() => 1),
  clearWatch: vi.fn(),
  getCurrentPosition: vi.fn(),
};

const mountPage = () =>
  shallowMount(DriverPage, {
    global: {
      stubs: {
        // DriverPage does not import vue-router; only <RouterLink> appears in its
        // template, so a plain global stub (no vue-router vi.mock) is all it needs.
        RouterLink: { props: ["to"], template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// A minimal active delivery-job payload exercising the page-own prop computeds bound
// to the (stubbed) active-job hero: nextAction (→ pickupLabelKey via business_type +
// status), activeReadyEta (food_ready_at), activeJobNavigateHref (pickup/delivery
// coords + status), fmtMoney and mapsLink.
const deliveryJob = (overrides = {}) => ({
  id: 5,
  status: "assigned",
  business_type: "restaurant",
  order_number: "D200",
  restaurant_name: "Test Kitchen",
  restaurant_slug: "test-kitchen",
  driver_payout: "18.00",
  order_total: "60.00",
  collect_cash: true,
  distance_km: 2.1,
  items_count: 2,
  pickup_lat: 33.5,
  pickup_lng: -7.6,
  pickup_address: "1 Pickup St",
  delivery_lat: 33.6,
  delivery_lng: -7.7,
  delivery_address: "9 Dropoff Ave",
  food_ready_at: null,
  ...overrides,
});

const APPROVED_ONLINE_STATUS = {
  data: {
    is_driver: true,
    driver_approved: true,
    is_driver_online: true,
    driver_vehicle_type: "motorbike",
  },
};

describe("DriverPage — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // The page reads/writes driver flags (welcomed / offer-sound) in localStorage;
    // clear first so a prior test's write can't leak into this one.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // jsdom has no navigator.geolocation — add it (preserving the real navigator's
    // other fields) BEFORE mount so the online auto-resume geo path runs for real
    // instead of early-returning at the `'geolocation' in navigator` guard.
    Object.defineProperty(navigator, "geolocation", {
      value: geoStub,
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    // onBeforeUnmount clears the job-poll interval, the 1s offer-countdown interval,
    // and the geo watch — unmount so none leak between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    try {
      delete navigator.geolocation;
    } catch {
      /* ignore */
    }
  });

  // ── (1) approved + ONLINE driver, no active job — auto-resume online shift ──
  // The core guard: the async onMounted (authenticate → fetchStatus → bootstrap →
  // startGeo + ensurePoll + the 1s countdown interval) must run without throwing.
  // This is the highest-value path — it fires navigator.geolocation.watchPosition at
  // mount, exactly the "browser API at setup()" class that white-screens in prod.
  it("mounts an approved, online driver (no active job) without a setup() crash", async () => {
    // setCustomer marks the store loaded, so onMounted's fetchCustomer() short-
    // circuits and the driver stays authenticated (isAuthenticated → true).
    useCustomerStore().setCustomer({ id: 1, name: "Driver", phone: "0600000000" });
    _routes = {
      "/driver/status/": APPROVED_ONLINE_STATUS,
      "/driver/jobs/": { data: { active: [], pending: [] } },
      "/driver/earnings/": {
        data: {
          available: "25.00",
          earned: "120.00",
          paid: "95.00",
          owed: "25.00",
          deliveries_today: 3,
          earned_today: "40.00",
          total_deliveries: 12,
          can_cash_out: true,
          cashout_min: "20.00",
        },
      },
      "/driver/cashout/": { data: { pending: null } },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Header (always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("driver.title");
    // Online-dashboard toggle label (own template, `online` branch) → confirms the
    // approved+online dashboard rendered rather than a loading/guest/pending branch.
    expect(wrapper.text()).toContain("driver.goOffline");
    // The auto-resume online shift actually reached startGeo() → watchPosition.
    expect(geoStub.watchPosition).toHaveBeenCalled();
  });

  // ── (2) guest (not signed in) — early-return onMounted path ──────────────────
  // fetchCustomer resolves an empty session → isAuthenticated false → onMounted
  // returns before fetchStatus/bootstrap. The rider-acquisition template renders and
  // no geo watch is started.
  it("mounts a signed-out visitor without a setup() crash", async () => {
    // No setCustomer + empty _routes → /customer/session/ resolves { data: {} } →
    // customer stays null → guest path.
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("driver.title");
    // Guest acquisition copy (own template, !isAuthenticated branch).
    expect(wrapper.text()).toContain("driver.earnTitle");
    // onMounted returned before bootstrap → no GPS watch for a guest.
    expect(geoStub.watchPosition).not.toHaveBeenCalled();
  });

  // ── (3) approved + online driver WITH an active delivery job ─────────────────
  // Even though the active-job hero is a stubbed child, shallowMount still evaluates
  // the page-own prop expressions bound to it — nextAction (→ pickupLabelKey),
  // activeReadyEta, activeJobNavigateHref, fmtMoney, mapsLink — so a crash in any of
  // those setup-time computeds fails here. The 5s active poll + wake-lock sync
  // (watch on [activeJob, activeRide, online]) also engage on this path.
  it("mounts an approved, online driver with an active delivery job without a crash", async () => {
    useCustomerStore().setCustomer({ id: 2, name: "Driver", phone: "0611111111" });
    _routes = {
      "/driver/status/": APPROVED_ONLINE_STATUS,
      "/driver/jobs/": { data: { active: [deliveryJob()], pending: [] } },
      "/driver/earnings/": { data: { available: "10.00", total_deliveries: 4 } },
      "/driver/cashout/": { data: { pending: null } },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("driver.title");
    // Approved dashboard chrome still renders alongside the (stubbed) active-job hero.
    expect(wrapper.text()).toContain("driver.goOffline");
  });
});
