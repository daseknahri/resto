/**
 * Mount smoke test for AdminPlatformAnalytics.vue (the platform-admin analytics
 * dashboard, ~298 lines — cross-tenant KPIs: outstanding money liabilities,
 * restaurants, customers/drivers, deliveries, rides, zones, flash sales, wallet,
 * and a revenue-by-vertical table). A read-only platform/admin surface.
 *
 * WHY: this is the app's recurring production bug class — an admin page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup, an
 * unguarded browser API, a bad Intl currency call) throws inside <script setup> and
 * was never caught by a test. This page's setup() wires ONE composable (useI18n),
 * builds `currency` (an Intl.NumberFormat currency:MAD over currentLocale.value),
 * and runs onMounted(refresh) → api.get('/admin/platform-analytics/'), then a second
 * Intl.DateTimeFormat over the same locale for the "last refreshed" stamp. shallowMount
 * runs the page's OWN setup() + own template (the header, the money/tenants/customers/
 * deliveries/rides/zones/flash-sales/wallet sections, and — page-own, not delegated —
 * the revenue-by-vertical table) while auto-stubbing the only child (the inline
 * `StatCard` render-function component registered in the second <script> block), so any
 * setup-time crash fails CI here instead of shipping a blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminCustomers.mount.test.js (URL-routed api mock
 * + real pinia + mocked useI18n), with the page-specific differences verified against
 * the source:
 *   1. The api boundary is ONLY `lib/api` (`import api from '../lib/api'` at line 227 —
 *      grep confirms there is NO `lib/adminApi` import). One mocked module, one
 *      URL-routed matcher. onMounted GETs /admin/platform-analytics/ (no params).
 *   2. The page imports NOTHING from vue-router (`grep "from 'vue-router'"` → no match)
 *      and renders NO <router-link> — so there is no router module to mock and no
 *      vi.hoisted RouterLink stub is needed.
 *   3. There is NO chart library — the KPI cards are an inline `StatCard`
 *      (defineComponent + h render function, second <script> block), which shallowMount
 *      stubs. So a StatCard's numeric/currency VALUE does NOT appear in wrapper.text().
 *      Case 2 therefore asserts on PAGE-OWN output only: the revenue-by-vertical table's
 *      own <td>{{ currency(row.total) }}</td> / <td>{{ row.count }}</td> cells and the
 *      v-if section heading — never a stubbed StatCard prop.
 *
 * CONTRACT NOTE (why "empty" is a zeroed skeleton, not `{ data: {} }`): the always-
 * rendered sections read nested fields WITHOUT null-guards (data.tenants.total,
 * data.customers.*, data.deliveries.*, data.zones.*, data.flash_sales.*, data.wallet.*).
 * A bare `{}` payload would throw a RENDER error (Cannot read properties of undefined),
 * not a setup() error — the page assumes the endpoint always returns the full shape.
 * The endpoint does exactly that (a fresh platform returns every section with zero
 * counts, never `{}`), so case 1 routes that real zeroed skeleton — the true "empty
 * platform" state — which still exercises the full data-branch render + the currency()
 * Intl path over zero money fields.
 *
 * Left REAL / not needed: the page wires NO Pinia store, NO interval / observer /
 * WebSocket / scrollIntoView at mount (onMounted is a single GET). setActivePinia is
 * kept for pattern parity and to guard any future store use; afterEach unmount settles
 * the in-flight mount fetch as hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminPlatformAnalytics is { t, currentLocale } — the mock MUST
// return both or the setup destructure throws, and currency() reads `currentLocale.value`
// as the locale arg of Intl.NumberFormat(currency:MAD) (and the refreshedAt DateTimeFormat).
// t echoes the key (params appended) so assertions can target the stable i18n keys the
// page's own template renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// One URL-routed matcher for the single mocked axios instance (lib/api). The mount GET
// (/admin/platform-analytics/) is routed per-test to a full-shape payload; the default
// `{ data: {} }` is only the fallback for any unmatched URL. _routes/_match are
// module-level and referenced ONLY from the lazy vi.fn closures below (which run at CALL
// time, never in the hoisted factory body) → TDZ-safe. get/post/put/patch/delete are all
// exposed (the page uses only api.get).
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

import AdminPlatformAnalytics from "../AdminPlatformAnalytics.vue";

const mountPage = () => shallowMount(AdminPlatformAnalytics);

// The real endpoint's zeroed structural skeleton: every always-rendered section present
// (unguarded by the template), money fields as numbers (0) so currency()'s Intl path runs
// even on the empty state. avg_driver_rating null → the "—" branch. Optional sections
// (financials / rides / revenue_by_vertical, all v-if-guarded) are omitted here.
const skeleton = () => ({
  tenants: { total: 0, active: 0, suspended: 0, canceled: 0 },
  customers: { total: 0, drivers_total: 0, drivers_online: 0 },
  deliveries: {
    total_jobs: 0,
    delivered: 0,
    active: 0,
    searching: 0,
    failed: 0,
    avg_driver_rating: null,
    total_fees: 0,
    total_driver_payouts: 0,
  },
  zones: { total: 0, active: 0 },
  flash_sales: { total: 0, live: 0, total_redemptions: 0 },
  wallet: {
    total_balance: 0,
    total_transactions: 0,
    total_bonus_issued: 0,
    total_payments: 0,
  },
});

describe("AdminPlatformAnalytics — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: any localStorage-backed store (staleCache) must start clean so a cache write
    // in one test can't be served as still-"fresh" to the next. (This page wires no store,
    // but the clear is convention-safe and cheap.)
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Unmount settles the in-flight mount fetch so nothing leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: the real zeroed "empty platform" skeleton ──────────
  // The core guard: the whole setup() (the useI18n wire, currency() Intl builder, the
  // onMounted GET /admin/platform-analytics/, the refreshedAt Intl.DateTimeFormat) and
  // the whole own-template must render with the endpoint's all-zero payload and not throw.
  // The header H1 title is the always-rendered crash anchor; the Restaurants section
  // heading confirms the data branch (v-else-if="data") rendered — i.e. the fetch resolved
  // and the full render walked every unguarded section without throwing.
  it("mounts with the empty (all-zero) platform skeleton without a setup() crash", async () => {
    _routes = { "/admin/platform-analytics/": { data: skeleton() } };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // onMounted → refresh → GET /admin/platform-analytics/

    expect(wrapper.exists()).toBe(true);
    // Header H1 (always rendered, page's own template) — the crash-guard anchor.
    // Exact key + namespace verified in i18n/messages-en.js: adminAnalytics.title.
    expect(wrapper.text()).toContain("adminAnalytics.title");
    // A section heading that renders ONLY in the data branch (v-else-if="data"), proving
    // the fetch resolved and the full section render walked without throwing.
    expect(wrapper.text()).toContain("adminAnalytics.sectionTenants");
  });

  // ── (2) loaded mount: rich payload incl. the optional v-if sections ───────
  // Drives the page's OWN loaded template — specifically the revenue-by-vertical table,
  // which is NOT delegated to the stubbed StatCard: its <td>{{ currency(row.total) }}</td>
  // and <td>{{ row.count }}</td> cells are the page's own output. (The KPI StatCards ARE
  // stubbed by shallowMount, so their numeric/currency values do not appear in text() —
  // hence the loaded assertion targets the table cells + the v-if section heading, not a
  // StatCard value.) This also exercises the optional financials/rides sections (each
  // v-if-guarded) + currency() over real money amounts.
  it("mounts with a loaded analytics payload (optional sections + revenue table) without a crash", async () => {
    _routes = {
      "/admin/platform-analytics/": {
        data: {
          ...skeleton(),
          tenants: { total: 42, active: 40, suspended: 1, canceled: 1 },
          customers: { total: 5000, drivers_total: 120, drivers_online: 33 },
          deliveries: {
            total_jobs: 9000,
            delivered: 8500,
            active: 50,
            searching: 10,
            failed: 40,
            avg_driver_rating: 4.7, // exercises the `+ ' ★'` branch (evaluated in parent render)
            total_fees: 123456.5,
            total_driver_payouts: 98765.25,
          },
          financials: {
            customer_wallet_liability: 25000,
            restaurant_float_outstanding: 8000,
            driver_owed: 3200,
          },
          rides: {
            total: 300,
            completed: 280,
            active: 5,
            cancelled: 15,
            fare_gmv: 15000,
            wallet_paid: 30,
            cash_paid: 12,
          },
          revenue_by_vertical: [
            { vertical: "food", total: 500000, count: 8842 },
            { vertical: "rides", total: 15000, count: 12 },
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminAnalytics.title");
    // The revenue-by-vertical section heading renders ONLY when data.revenue_by_vertical
    // is present (v-if) — a page-own <h2>, and the loaded-path discriminator.
    expect(text).toContain("adminAnalytics.sectionRevenueByVertical");
    // A revenue row's `count` rendered raw in the page's OWN <td> (NOT a stubbed StatCard),
    // proving the revenue-table v-for rendered numeric page-own cells. 8842 is distinctive
    // (chosen to not collide with any t-param-echoed number).
    expect(text).toContain("8842");
  });
});
