/**
 * Mount smoke test for AdminDeliveryJobs.vue (the platform-admin delivery-jobs
 * monitor, ~233 lines — every delivery job across all tenants: status, driver,
 * restaurant, payout, live poll).
 *
 * WHY: this is the app's recurring production bug class — an admin/ops page
 * white-screens because a setup()-time error (a TDZ ReferenceError, an undefined
 * lookup, an unguarded browser API, a bad Intl currency call) throws inside
 * <script setup> and was never caught by a test. AdminDeliveryJobs' setup() wires
 * one composable (useI18n), builds `fmtMoney` (an Intl.NumberFormat currency:MAD
 * over currentLocale.value) and `fmtDate` (Intl.DateTimeFormat), maps status →
 * label (with the at_restaurant branch delegating to the pure `pickupLabelKey`
 * helper), and runs an onMounted that fires a single GET /admin/delivery-jobs/,
 * registers a 20s setInterval poll, and adds a document 'visibilitychange'
 * listener. shallowMount runs the page's OWN setup() + own template (the header,
 * the status-filter chips, and — in the loaded path — BOTH the desktop jobs table
 * AND the mobile card list, each a v-for over `jobs`) while auto-stubbing the only
 * child (AppIcon), so any setup-time crash fails CI here instead of shipping a
 * blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminRides.mount.test.js +
 * AdminCustomers.mount.test.js (URL-routed api mock + real pinia + mocked useI18n),
 * with the page-specific differences verified against the source:
 *   1. The api boundary is ONLY `lib/api` (`import api from '../lib/api'`, line 139
 *      — grep confirms there is NO `lib/adminApi` on this page, unlike AdminRides).
 *      One mocked module, one URL-routed matcher. onMounted GETs
 *      /admin/delivery-jobs/ (with a `{ params }` arg the matcher ignores). The
 *      list handler is `Array.isArray(res.data) ? res.data : (res.data?.results
 *      || [])`, so the default `{ data: {} }` → not-an-array → results undefined →
 *      `[]` → the empty-state branch renders. The loaded payload is therefore a
 *      BARE ARRAY under `data` (not `{ results }`), unlike AdminCustomers.
 *   2. The page imports NOTHING from vue-router (`grep "router-link|RouterLink|
 *      vue-router"` → no match) and renders NO <router-link> — so there is no
 *      router module to mock and no vi.hoisted RouterLink stub is needed.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - `pickupLabelKey` from lib/deliveryVocab — a pure (businessType, variant) →
 *     i18n-key string function, only reached from statusLabel when a job's status
 *     is 'at_restaurant'. Case 2 includes one such job so this real branch runs.
 * The page registers a 20s `setInterval(fetchJobs)` (POLL_MS, line 221) + a
 * document 'visibilitychange' listener at mount, and onUnmounted clears BOTH
 * (clearInterval + removeEventListener, lines 227-232). The 20s interval never
 * elapses within a test, and afterEach unmount runs that onUnmounted so neither the
 * timer nor the listener leaks between tests (mirrors AdminRides/OwnerHome afterEach).
 * No observer / scrollIntoView / WebSocket is used at mount, so no jsdom stubs are needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminDeliveryJobs is { t, currentLocale } — the mock MUST
// return both or the setup destructure throws, and fmtMoney/fmtDate read
// `currentLocale.value` as the locale arg of Intl.NumberFormat(currency:MAD) /
// Intl.DateTimeFormat. t echoes the key (params appended) so assertions can target
// the stable i18n keys the page's own template renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// One URL-routed matcher for the single mocked axios instance (lib/api). The one
// mount GET (/admin/delivery-jobs/) defaults to `{ data: {} }` so the empty path
// renders; a test sets _routes to drive the loaded path. _routes/_match are
// module-level and referenced ONLY from the lazy vi.fn closures below (which run at
// CALL time, never in the hoisted factory body) → TDZ-safe. Exposes
// get/post/put/patch/delete for shape-parity (the page only uses api.get).
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

import AdminDeliveryJobs from "../AdminDeliveryJobs.vue";

const mountPage = () => shallowMount(AdminDeliveryJobs);

// A realistic delivery-job row as the /admin/delivery-jobs/ list ships it:
// order_number, tenant name/id, a nested driver object, business_type, status, a
// STRING driver_payout (as the API serializes decimals), and a created_at ISO — the
// exact fields the table + card-list v-fors read.
const job = (overrides = {}) => ({
  id: 9001,
  order_number: "1042",
  tenant_id: 3,
  tenant_name: "Pizza Palace",
  driver: { id: 7, name: "Mohamed Driver", phone: "0622334455" },
  business_type: "restaurant",
  status: "delivered",
  driver_payout: "18.50",
  created_at: "2026-02-01T10:25:00Z",
  ...overrides,
});

describe("AdminDeliveryJobs — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: any localStorage-backed store (staleCache) must start clean so a cache
    // write in one test can't be served as still-"fresh" to the next.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // AdminDeliveryJobs registers a 20s setInterval poll + a 'visibilitychange'
    // listener at mount; unmount runs onUnmounted → clearInterval +
    // removeEventListener so neither leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: empty jobs list ────────────────────────────────────
  // The core guard: the whole setup() (the useI18n wire, fmtMoney + fmtDate, the
  // status-label maps, the onMounted GET /admin/delivery-jobs/ + the interval/
  // listener registration) and the whole own-template must render with empty data
  // and not throw. The H1 title is the always-rendered crash anchor; the empty-state
  // key confirms the jobs fetch resolved down its empty branch (default { data: {} }
  // → not an array → results undefined → [] → !jobs.length → empty state).
  it("mounts with an empty jobs list (default mount GET) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetchJobs → GET /admin/delivery-jobs/

    expect(wrapper.exists()).toBe(true);
    // Header H1 (always rendered, page's own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminDeliveryJobs.title");
    // Empty /admin/delivery-jobs/ (default { data: {} } → jobs.length 0) → the
    // empty-state branch, confirming the jobs-table path resolved without throwing.
    expect(wrapper.text()).toContain("adminDeliveryJobs.empty");
  });

  // ── (2) loaded mount: real jobs (assigned+delivered + unassigned+searching + at_restaurant) ──
  // Drives the page's OWN loaded templates (no child delegation): the desktop jobs
  // table v-for AND the mobile card-list v-for over `jobs` (order_number /
  // tenant_name-or-#id / driver-name-or-phone-or-unassigned branch /
  // statusClass+statusLabel — incl. the at_restaurant → pickupLabelKey branch /
  // fmtMoney(driver_payout) Intl-currency + fmtDate(created_at) Intl-date). These
  // are the array-render + Intl paths that only run with a non-empty jobs array.
  it("mounts with a loaded jobs list (assigned + unassigned + at_restaurant rows, string payouts) without a crash", async () => {
    _routes = {
      "/admin/delivery-jobs/": {
        data: [
          job({ id: 9001, status: "delivered", tenant_name: "Pizza Palace" }),
          job({
            id: 9002,
            order_number: "1043",
            tenant_name: "", // → falls back to '#' + tenant_id in the template
            tenant_id: 5,
            driver: null, // exercises the "unassigned" v-else branch
            status: "searching",
            driver_payout: "0.00",
            created_at: "2026-02-02T09:00:00Z",
          }),
          job({
            id: 9003,
            order_number: "1044",
            driver: { id: 8, phone: "0633445566" }, // no name → phone fallback
            status: "at_restaurant", // → statusLabel delegates to pickupLabelKey
            business_type: "pharmacy", // → deliveryVocab.atPickupPharmacy
            driver_payout: "12.00",
          }),
        ],
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminDeliveryJobs.title");
    // Loaded table branch: colOrder renders ONLY in the v-else data-views block
    // (jobs.length && !loading && !fetchError), so it proves the loaded path ran.
    expect(text).toContain("adminDeliveryJobs.colOrder");
    // A job row rendered from the fetched payload (own-template v-for, not a stubbed
    // child) — the loaded discriminator (appears nowhere in the empty/chrome path).
    expect(text).toContain("Pizza Palace");
    // status:'delivered' → statusLabel via the static STATUS_LABELS map.
    expect(text).toContain("adminDeliveryJobs.statusDelivered");
    // The driver-less second job → the "unassigned" label, which renders ONLY inside
    // the jobs v-for's `v-else` (never in the header/chips), proving the mixed-row
    // array-render path ran.
    expect(text).toContain("adminDeliveryJobs.unassigned");
    // The at_restaurant + pharmacy job → statusLabel delegates to the real
    // pickupLabelKey helper → deliveryVocab.atPickupPharmacy, proving that branch ran.
    expect(text).toContain("deliveryVocab.atPickupPharmacy");
  });
});
