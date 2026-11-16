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
import api from "../../lib/api";

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
// ── S4-A / C-17 ────────────────────────────────────────────────────────────────
// fetchCashout polls on the adaptive interval (15 s idle, no active job/ride).
// A failed poll must NOT clear the last-good pending code; only a successful
// response with no pending request clears it. Driven through the real poll
// timer (fake timers) + the real api mock, asserting on the rendered code /
// "code active" chip (the code digits live in the collapsed wallet panel).
describe("DriverPage — C-17 cash-out poll failure keeps the last-good code", () => {
  let wrapper;
  let cashoutShouldFail = false;

  beforeEach(() => {
    // Own isolation — never rely on the base describe's hook (S2-B lesson).
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    cashoutShouldFail = false;
    vi.clearAllMocks();
    api.get.mockImplementation((url) =>
      cashoutShouldFail && url.includes("/driver/cashout/")
        ? Promise.reject(new Error("cash-out poll down"))
        : Promise.resolve(_match(url)),
    );
    api.post.mockImplementation(() => Promise.resolve({ data: {} }));
    Object.defineProperty(navigator, "geolocation", {
      value: geoStub,
      configurable: true,
      writable: true,
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    cashoutShouldFail = false;
    vi.useRealTimers();
    try {
      delete navigator.geolocation;
    } catch {
      /* ignore */
    }
  });

  const mountWithPendingCashout = async () => {
    useCustomerStore().setCustomer({ id: 1, name: "Driver", phone: "0600000000" });
    _routes = {
      "/driver/status/": APPROVED_ONLINE_STATUS,
      "/driver/jobs/": { data: { active: [], pending: [] } },
      "/driver/earnings/": {
        data: {
          available: "50.00",
          earned: "120.00",
          paid: "70.00",
          owed: "50.00",
          deliveries_today: 1,
          earned_today: "20.00",
          total_deliveries: 5,
          can_cash_out: true,
          cashout_min: "20.00",
        },
      },
      // Expires an hour out so the 1 s countdown clock never drops it mid-test.
      "/driver/cashout/": {
        data: {
          pending: {
            id: 7,
            amount: "50.00",
            code: "482913",
            expires_at: new Date(Date.now() + 3600_000).toISOString(),
          },
        },
      },
    };
    wrapper = mountPage();
    // waitFor settles the async onMounted chain (fetchCustomer → fetchStatus →
    // bootstrap → fetchCashout) while advancing the fake timers.
    await vi.waitFor(() => expect(wrapper.text()).toContain("driver.goOffline"));
    await vi.waitFor(() => expect(wrapper.text()).toContain("driver.cashoutCodeActive"));
  };

  const openWallet = async () => {
    const trigger = wrapper.find('button[aria-controls="driver-wallet-panel"]');
    expect(trigger.exists()).toBe(true);
    await trigger.trigger("click");
    await vi.advanceTimersByTimeAsync(0);
  };

  it("keeps showing the pending code when the next cash-out poll fails", async () => {
    await mountWithPendingCashout();
    await openWallet();
    expect(wrapper.text()).toContain("482913");

    cashoutShouldFail = true;
    // One idle poll tick (15 s): fetchJobs + fetchEarnings + fetchCashout (fails).
    await vi.advanceTimersByTimeAsync(15000);
    await vi.advanceTimersByTimeAsync(0);

    // Pre-fix behaviour cleared the code here (cashout.value = null in the catch).
    expect(wrapper.text()).toContain("482913");
    expect(wrapper.text()).toContain("driver.cashoutCodeActive");
  });

  it("clears the code when a poll succeeds with no pending request", async () => {
    await mountWithPendingCashout();
    await openWallet();
    expect(wrapper.text()).toContain("482913");

    _routes["/driver/cashout/"] = { data: { pending: null } };
    await vi.advanceTimersByTimeAsync(15000);
    await vi.advanceTimersByTimeAsync(0);

    expect(wrapper.text()).not.toContain("482913");
    expect(wrapper.text()).not.toContain("driver.cashoutCodeActive");
  });
});

// ── S4-A / C-23 ────────────────────────────────────────────────────────────────
// submitCashout with a non-numeric / zero / negative amount must show the
// specific "enter a valid amount" message — not the generic error. Driven
// through the stubbed DriverCashoutModal's v-model + submit events (the modal
// is a shallowMount stub, so its $emit drives the parent's v-model listener
// and @submit handler exactly as the real modal would).
describe("DriverPage — C-23 cash-out amount validation shows a specific error", () => {
  let wrapper;

  beforeEach(() => {
    // Own isolation — never rely on the base describe's hook (S2-B lesson).
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    api.post.mockImplementation(() => Promise.resolve({ data: {} }));
    Object.defineProperty(navigator, "geolocation", {
      value: geoStub,
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    try {
      delete navigator.geolocation;
    } catch {
      /* ignore */
    }
  });

  // shallowMount auto-stubs the modal; its name is the component name (or the
  // name + "Stub" in some VTU builds) — try both so the lookup is not brittle.
  const cashoutModal = () => {
    const byName = wrapper.findComponent({ name: "DriverCashoutModal" });
    if (byName.exists()) return byName;
    const byStubName = wrapper.findComponent({ name: "DriverCashoutModalStub" });
    if (byStubName.exists()) return byStubName;
    throw new Error("DriverCashoutModal stub not found (tried DriverCashoutModal / DriverCashoutModalStub)");
  };

  const mountWithCashoutModalOpen = async () => {
    useCustomerStore().setCustomer({ id: 3, name: "Driver", phone: "0622222222" });
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
    wrapper = mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain("driver.goOffline");
    await wrapper.find('button[aria-controls="driver-wallet-panel"]').trigger("click");
    const cashOutButton = wrapper
      .findAll("button")
      .find((b) => b.text().includes("driver.cashOut"));
    expect(cashOutButton).toBeDefined();
    await cashOutButton.trigger("click");
    await flushPromises();
    expect(cashoutModal().props("open")).toBe(true);
  };

  const submitAmount = async (amount) => {
    const modal = cashoutModal();
    await modal.vm.$emit("update:amount", amount);
    await modal.vm.$emit("submit");
    await flushPromises();
  };

  it("shows the specific invalid-amount message for zero (no network call)", async () => {
    await mountWithCashoutModalOpen();
    await submitAmount("0");
    expect(cashoutModal().props("error")).toBe("driver.cashoutInvalidAmount");
    expect(cashoutModal().props("open")).toBe(true);
    expect(api.post).not.toHaveBeenCalledWith("/driver/cashout/", expect.anything());
  });

  it("shows the specific invalid-amount message for a non-numeric amount (no network call)", async () => {
    await mountWithCashoutModalOpen();
    await submitAmount("abc");
    expect(cashoutModal().props("error")).toBe("driver.cashoutInvalidAmount");
    expect(cashoutModal().props("open")).toBe(true);
    expect(api.post).not.toHaveBeenCalledWith("/driver/cashout/", expect.anything());
  });

  it("shows the specific invalid-amount message for a negative amount (no network call)", async () => {
    await mountWithCashoutModalOpen();
    await submitAmount("-5");
    expect(cashoutModal().props("error")).toBe("driver.cashoutInvalidAmount");
    expect(cashoutModal().props("open")).toBe(true);
    expect(api.post).not.toHaveBeenCalledWith("/driver/cashout/", expect.anything());
  });

  it("submits a valid amount and closes the modal without the error", async () => {
    await mountWithCashoutModalOpen();
    await submitAmount("10");
    expect(api.post).toHaveBeenCalledWith("/driver/cashout/", { amount: 10 });
    expect(cashoutModal().props("error")).toBe("");
    expect(cashoutModal().props("open")).toBe(false);
  });
});
