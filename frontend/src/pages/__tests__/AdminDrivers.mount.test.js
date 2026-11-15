/**
 * Mount smoke test for AdminDrivers.vue (the platform-admin drivers page, ~590 lines).
 *
 * WHY: this is the app's recurring production bug class — an admin/money page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup, an unguarded
 * browser API, a bad Intl currency call) throws inside <script setup> and was never caught
 * by a test. AdminDrivers' setup() wires three composables/stores (useI18n / useConfirmModal /
 * useToastStore), builds `fmtMoney` (an Intl.NumberFormat currency:MAD over currentLocale.value)
 * and `formatDate` (Intl.DateTimeFormat), exposes four order-derived computeds
 * (onlineCount / pendingCount / sortedDrivers / totalDeliveries), and runs an onMounted that
 * fires a single GET /admin/drivers/. shallowMount runs the page's OWN setup() + own template
 * (the stats bar, the desktop drivers table AND the mobile card list — both v-for over
 * sortedDrivers, plus the earnings slide-over shell) while auto-stubbing nothing heavy (the
 * page has no child components), so any setup-time crash fails CI here instead of shipping a
 * blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminWallet.mount.test.js + AdminConsole.mount.test.js
 * (URL-routed api mock + real pinia + mocked useI18n), with the page-specific differences
 * verified against the source:
 *   1. The api boundary is ONLY `lib/api` (`grep "import (api|adminApi) from"` → single hit
 *      `import api from '../lib/api'`, line 423). There is NO `lib/adminApi` on this page — so
 *      only ../../lib/api is mocked. It exposes get/post/put/patch/delete (the page uses
 *      api.get + api.post; the others are provided for shape-parity and safety).
 *   2. The page imports NOTHING from vue-router (`grep "from 'vue-router'"` → no match) and
 *      renders NO <router-link> in its template (plain <a :href> anchors only) — so there is no
 *      router module to mock and no RouterLink stub is needed.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - the toast store (real Pinia).
 *   - useConfirmModal (module-level ref singletons; `confirm` only fires on a user action —
 *     payout / approve / reject / car-approve — never at mount).
 *   - newIdempotencyKey (only called from submitPayout, a user-action handler).
 * The page registers NO interval / poll / observer / WebSocket / scrollIntoView at mount — it
 * fetches once in onMounted and only re-fetches on the manual "Refresh" button — so there is
 * nothing timer-like to fake here. The earnings slide-over (a <Teleport>/<Transition>) has its
 * content behind `v-if="selected"` and `selected` is null at mount, so nothing renders inside;
 * Teleport/Transition are stubbed to render their slot inline (mirrors OwnerHome.mount.test.js)
 * purely to keep shallowMount from teleporting an inert (v-if=false) subtree to document.body.
 * afterEach unmounts to settle the in-flight mount fetch between tests.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminDrivers is { t, currentLocale } — the mock MUST return both or
// the setup destructure throws, and fmtMoney/formatDate read `currentLocale.value` as the
// locale arg of Intl.NumberFormat(currency:MAD) / Intl.DateTimeFormat. t echoes the key
// (params appended) so assertions can target the stable i18n keys the page's own template
// renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed matcher for the single mocked axios instance (lib/api). The one mount GET
// (/admin/drivers/) defaults to `{ data: {} }` so the empty path renders; a test sets _routes
// to drive the loaded path. _routes/_match are module-level and referenced ONLY from the lazy
// vi.fn closures below (which run at CALL time, never in the hoisted factory body) → TDZ-safe.
// Exposes get/post/put/patch/delete since the page uses api.get + api.post.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import AdminDrivers from "../AdminDrivers.vue";
import api from "../../lib/api";

const mountDrivers = () =>
  shallowMount(AdminDrivers, {
    global: {
      stubs: {
        // Inert at mount (content is behind v-if="selected", selected=null) — render the slot
        // inline instead of teleporting an empty subtree to document.body.
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

// A realistic driver row as the /admin/drivers/ list ships it (owed is a STRING amount, as the
// API serializes decimals). Includes name / phone / email / approval + online state / vehicle
// + the per-row stat fields the stats bar + table + mobile list read.
const driver = (overrides = {}) => ({
  id: 1,
  name: "Mohamed Driver",
  email: "m@example.com",
  phone: "0611111111",
  approved: true,
  is_online: true,
  driver_lat: 33.57,
  driver_lng: -7.59,
  total_jobs: 20,
  completed_jobs: 18,
  avg_rating: 4.8,
  owed: "125.50",
  created_at: "2026-01-01T10:00:00Z",
  vehicle: "Dacia Logan",
  driver_vehicle_type: "car",
  ...overrides,
});

describe("AdminDrivers — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: the toast store is localStorage-backed (staleCache); clear it FIRST so a cache
    // write in one test can't be served as still-"fresh" to the next.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No interval/listener/WS is registered at mount, but unmount settles the in-flight
    // /admin/drivers/ mount fetch so nothing leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: empty drivers list ─────────────────────────────────
  // The core guard: the whole setup() (three composable/store wires, fmtMoney + formatDate,
  // the four lazy computeds, the onMounted GET /admin/drivers/) and the whole own-template must
  // render with empty data and not throw. The header title is the always-rendered crash anchor;
  // the empty-state key confirms the drivers fetch resolved down its empty branch (default
  // { data: {} } → drivers.length falsy → empty state, and the array computeds in the v-else
  // block are never evaluated).
  it("mounts with an empty drivers list (default mount GET) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountDrivers();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetchDrivers → GET /admin/drivers/

    expect(wrapper.exists()).toBe(true);
    // Header title (always rendered, page's own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminDrivers.title");
    // Empty /admin/drivers/ (default { data: {} } → drivers.length falsy) → the empty-state
    // branch, confirming the list path resolved without throwing.
    expect(wrapper.text()).toContain("adminDrivers.empty");
  });

  // ── (2) loaded mount: real drivers (approved+online + pending) ─────────────
  // Drives the page's OWN loaded templates (no child delegation): the stats bar
  // (onlineCount / pendingCount / totalDeliveries reduce), the desktop drivers table v-for AND
  // the mobile card list v-for over sortedDrivers (name / phone / approval + online status
  // labels / avg_rating / fmtMoney(owed) Intl-currency + formatDate(created_at) Intl-date).
  // These are the array-render + Intl paths that only run with a non-empty drivers array.
  it("mounts with a loaded drivers list (approved+online + pending, string owed) without a crash", async () => {
    _routes = {
      "/admin/drivers/": {
        data: [
          driver({ id: 1, name: "Mohamed Driver", approved: true, is_online: true }),
          driver({
            id: 2,
            name: "Sara Pending",
            email: undefined,
            phone: "0622222222",
            approved: false,
            is_online: false,
            driver_lat: null,
            driver_lng: null,
            total_jobs: 0,
            completed_jobs: 0,
            avg_rating: null,
            owed: "0.00",
            created_at: "2026-02-01T10:00:00Z",
            vehicle: "",
            driver_vehicle_type: "moto",
          }),
        ],
      },
    };

    expect(() => {
      wrapper = mountDrivers();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminDrivers.title");
    // Driver row rendered from the fetched payload (own-template v-for, not a stubbed child).
    expect(text).toContain("Mohamed Driver");
    // Status label from the page's own v-for: approved + is_online → statusOnline (the
    // approved-branch label). Its presence proves the sortedDrivers array-render path ran.
    expect(text).toContain("adminDrivers.statusOnline");
    // Pending driver → the !approved badge (pendingCount label), proving the mixed-state
    // sort/branch rendered too.
    expect(text).toContain("adminDrivers.pendingCount");
  });
});

/**
 * MERGE NOTE (Run 8 G3a): append this describe block to
 * frontend/src/pages/__tests__/AdminDrivers.mount.test.js (after pulling it),
 * adapting the _routes / mount helper names to that file's existing ones.
 * Assumes the file's existing URL-routed api mock + mocked useI18n (keys render
 * as `ns.key` / `ns.key({json})`, as in AdminRides.mount.test.js).
 *
 * Covers:
 *   A2-08 — stats bar uses the server stats (full set, not the capped rows)
 *           and the "showing first 200 of N" note appears when total > 200.
 */

const driverRow = (id, overrides = {}) => ({
  id,
  name: `Driver ${id}`,
  phone: "0612345678",
  email: "",
  approved: true,
  vehicle: "Scooter",
  driver_vehicle_type: "scooter",
  driver_licence_url: "",
  driver_insurance_url: "",
  driver_car_approved: false,
  driver_licence_expiry: null,
  driver_insurance_expiry: null,
  is_online: false,
  driver_lat: null,
  driver_lng: null,
  position_updated_at: null,
  total_jobs: 10,
  completed_jobs: 8,
  avg_rating: 4.5,
  earned: "200.00",
  paid: "100.00",
  owed: "100.00",
  driver_rejected_at: null,
  driver_rejection_reason: "",
  created_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

const findButton = (wrapper, text) =>
  wrapper.findAll("button").find((b) => b.text().includes(text));

describe("AdminDrivers — server stats + cap note (A2-08)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  it("stats bar uses server stats and the cap note shows when total > 200", async () => {
    _routes = {
      "/admin/drivers/": {
        data: {
          results: [driverRow(1), driverRow(2, { is_online: true, approved: false, completed_jobs: 5 })],
          total: 250,
          limit: 200,
          stats: { total: 250, online: 90, pending: 12, total_deliveries: 1234 },
        },
      },
    };
    wrapper = mountDrivers();
    await flushPromises();
    const text = wrapper.text();
    // Server stats (full set), not the 2 loaded rows: 250 drivers, 90 online,
    // 12 pending, 1234 deliveries.
    expect(text).toContain("250");
    expect(text).toContain("90");
    expect(text).toContain("12");
    expect(text).toContain("1234");
    expect(text).toContain('adminDrivers.showingFirst({"shown":2,"total":250})');
  });

  it("no cap note when the list fits under 200", async () => {
    _routes = {
      "/admin/drivers/": {
        data: {
          results: [driverRow(1)],
          total: 1,
          limit: 200,
          stats: { total: 1, online: 0, pending: 0, total_deliveries: 8 },
        },
      },
    };
    wrapper = mountDrivers();
    await flushPromises();
    expect(wrapper.text()).not.toContain("adminDrivers.showingFirst");
  });
});

describe("AdminDrivers — payout cap on the delivery ledger (A2-09)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  const openDriverWithEarnings = async (earnings) => {
    _routes = {
      // Earnings first: _match is substring-first-match, and the list key
      // "/admin/drivers/" would shadow "/admin/drivers/1/earnings/".
      "/admin/drivers/1/earnings/": { data: earnings },
      "/admin/drivers/": {
        data: {
          results: [driverRow(1)],
          total: 1,
          limit: 200,
          stats: { total: 1, online: 0, pending: 0, total_deliveries: 8 },
        },
      },
    };
    wrapper = mountDrivers();
    await flushPromises();
    await wrapper.vm.openDriver(driverRow(1));
    await flushPromises();
    return wrapper;
  };

  const earningsPayload = (overrides = {}) => ({
    driver_id: 1,
    name: "Driver 1",
    phone: "0612345678",
    earned: "100.00",
    paid: "40.00",
    owed: "100.00",
    wallet_balance: "100.00",
    ledger_owed: "60.00",
    cashout_total: "40.00",
    deliveries: [],
    payouts: [],
    ...overrides,
  });

  it("prefills the payout amount on min(ledger_owed, wallet_balance) and shows the cap note", async () => {
    await openDriverWithEarnings(earningsPayload());
    const input = wrapper.find('input[type="number"]');
    expect(input.element.value).toBe("60.00");
    expect(input.attributes("max")).toBe("60");
    expect(wrapper.text()).toContain("adminDrivers.payoutCapNote");
  });

  it("hides the payout form when the ledger cap is 0 even if the wallet holds cash", async () => {
    await openDriverWithEarnings(earningsPayload({ ledger_owed: "0.00", cashout_total: "60.00" }));
    expect(wrapper.text()).not.toContain("adminDrivers.recordPayout");
  });
});

describe("AdminDrivers — car-doc expiries (A2-10)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  const carDriver = (overrides = {}) => driverRow(3, {
    driver_vehicle_type: "car",
    driver_licence_url: "https://cdn/lic.jpg",
    driver_insurance_url: "https://cdn/ins.jpg",
    driver_licence_expiry: "2027-06-01",
    driver_insurance_expiry: "2027-12-31",
    ...overrides,
  });

  const openCarDriver = async (row) => {
    _routes = {
      // Earnings first: _match is substring-first-match (see above).
      "/admin/drivers/3/earnings/": {
        data: { driver_id: 3, name: "Driver 3", phone: "", earned: "0", paid: "0", owed: "0", wallet_balance: "0", ledger_owed: "0", cashout_total: "0", deliveries: [], payouts: [] },
      },
      "/admin/drivers/": {
        data: {
          results: [row],
          total: 1,
          limit: 200,
          stats: { total: 1, online: 0, pending: 0, total_deliveries: 0 },
        },
      },
    };
    wrapper = mountDrivers();
    await flushPromises();
    await wrapper.vm.openDriver(row);
    await flushPromises();
    return wrapper;
  };

  it("flags an expired licence and blocks the approve click (no POST)", async () => {
    await openCarDriver(carDriver({ driver_licence_expiry: "2020-01-01" }));
    expect(wrapper.text()).toContain("adminConsole.expiryExpired");
    await findButton(wrapper, "adminConsole.carApprove").trigger("click");
    await flushPromises();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("approve sends the entered expiry dates", async () => {
    await openCarDriver(carDriver());
    api.post.mockResolvedValue({ data: { driver_car_approved: true, driver_licence_expiry: "2027-06-01", driver_insurance_expiry: "2027-12-31" } });
    await findButton(wrapper, "adminConsole.carApprove").trigger("click");
    await flushPromises();
    expect(api.post).toHaveBeenCalledWith(
      "/admin/drivers/3/car-approve/",
      { licence_expiry: "2027-06-01", insurance_expiry: "2027-12-31" },
    );
  });
});
