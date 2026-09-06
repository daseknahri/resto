/**
 * Mount smoke test for AdminCustomers.vue (the platform-admin customers page,
 * ~560 lines — every customer across all tenants: search, wallet credit, loyalty,
 * driver toggle, cross-restaurant order history + ledger). A MONEY/admin surface.
 *
 * WHY: this is the app's recurring production bug class — an admin page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup, an
 * unguarded browser API, a bad Intl currency call) throws inside <script setup> and
 * was never caught by a test. AdminCustomers' setup() wires four composables/stores
 * (useI18n / useConfirmModal / useFocusTrap / useToastStore), builds `fmtMoney` (an
 * Intl.NumberFormat currency over currentLocale.value) + `fmtDate` (Intl.DateTimeFormat),
 * and runs onMounted(fetchCustomers) → api.get('/admin/customers/'). shallowMount runs
 * the page's OWN setup() + own template (the header, search toolbar, the desktop
 * customers table AND the mobile card list — both v-for the same array) while
 * auto-stubbing the only child (AppIcon), so any setup-time crash fails CI here
 * instead of shipping a blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminWallet.mount.test.js +
 * pages/__tests__/OwnerReservations.mount.test.js (URL-routed api mock + real pinia +
 * mocked useI18n), with the page-specific differences verified against the source:
 *   1. The api boundary is ONLY `lib/api` (`import api from '../lib/api'` — grep
 *      confirms there is NO `lib/adminApi` import, unlike AdminWallet). One mocked
 *      module, one URL-routed matcher. onMounted GETs /admin/customers/ (with a
 *      `{ params }` arg the matcher ignores). Default `{ data: {} }` → `results`
 *      undefined → `customers = []` → the empty-state branch renders.
 *   2. The page imports NOTHING from vue-router (`grep "from 'vue-router'"` → no
 *      match) and renders NO <router-link> — so there is no router module to mock and
 *      no vi.hoisted RouterLink stub is needed.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - the toast store (real Pinia).
 *   - useConfirmModal (module-level ref singletons; `confirm` only fires on the
 *     credit-wallet user action, never at mount).
 *   - useFocusTrap (at setup it registers only a lazy watch on the `!!selected`
 *     computed + onBeforeUnmount; it binds a document 'keydown' listener ONLY when the
 *     detail slide-over opens — `selected` is null at mount, so nothing is bound).
 *   - newIdempotencyKey (only called from creditWallet, a user action).
 * The detail slide-over is `<Teleport to="body"><... v-if="selected">`; `selected` is
 * null at mount so the Teleport renders nothing (no focus-trap keydown, no detail
 * fetch). Case 2 therefore stays a pure list-render assertion — the loaded detail
 * panel is behind a row click and is out of scope for a mount smoke test. The page
 * registers NO interval / observer / WebSocket / scrollIntoView at mount (the lone
 * setTimeout lives in onSearch, user-triggered), so there is nothing timer-like to
 * fake here; afterEach unmount settles the in-flight mount fetch as hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminCustomers is { t, currentLocale } — the mock MUST return
// both or the setup destructure throws, and fmtMoney reads `currentLocale.value` as the
// locale arg of Intl.NumberFormat(currency). t echoes the key (params appended) so
// assertions can target the stable i18n keys the page's own template renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// One URL-routed matcher for the single mocked axios instance (lib/api). The mount GET
// (/admin/customers/) defaults to `{ data: {} }` so the empty path renders; a test sets
// _routes to drive the loaded path. _routes/_match are module-level and referenced ONLY
// from the lazy vi.fn closures below (which run at CALL time, never in the hoisted
// factory body) → TDZ-safe. get/post/patch/delete are all exposed (the page uses
// api.get/post/patch).
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

import AdminCustomers from "../AdminCustomers.vue";

const mountPage = () => shallowMount(AdminCustomers);

// A realistic customer row with the fields the page's own list template reads:
// id, name, phone/email, phone_verified, wallet_balance (STRING, as the API ships it),
// loyalty_points, is_driver, created_at.
const customer = (overrides = {}) => ({
  id: 1,
  name: "Aicha Benali",
  phone: "0611223344",
  phone_verified: true,
  email: "aicha@example.com",
  wallet_balance: "125.50",
  loyalty_points: 340,
  is_driver: false,
  created_at: "2026-08-20T12:00:00Z",
  ...overrides,
});

describe("AdminCustomers — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: stores (toast) can be localStorage-backed (staleCache); clear it FIRST so a
    // cache write in one test can't be served as still-"fresh" to the next.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Unmount settles the in-flight mount fetch and tears down useFocusTrap's watch /
    // onBeforeUnmount so nothing leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: empty customers list ───────────────────────────────
  // The core guard: the whole setup() (four composable/store wires, fmtMoney/fmtDate,
  // the onMounted GET /admin/customers/) and the whole own-template must render with
  // empty data and not throw. The H1 title is the always-rendered crash anchor; the
  // empty-state confirms the customers fetch resolved down its empty branch
  // (data.results undefined → [] → !customers.length).
  it("mounts with empty data (default-empty customers GET) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetchCustomers

    expect(wrapper.exists()).toBe(true);
    // Header H1 (always rendered, page's own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminCustomers.title");
    // Empty /admin/customers/ (default { data: {} } → results falsy → customers.length 0)
    // → the empty-state branch, confirming the customers-table path resolved without throwing.
    expect(wrapper.text()).toContain("adminCustomers.empty");
  });

  // ── (2) loaded mount: real customers payload (string wallet amounts) ──────
  // Drives the page's OWN loaded templates (not delegated to a stubbed child): the
  // customers v-for (rendered in both the desktop table and the mobile card list —
  // jsdom renders both regardless of the CSS md:/md:hidden classes), exercising
  // fmtMoney (Intl currency over the string wallet_balance + the parseFloat(...) > 0
  // branch), fmtDate(created_at), the loyalty_points render, and the is_driver chip.
  // These are the array-render + Intl paths that only run with a non-empty payload.
  it("mounts with a loaded customers table (string amounts) without a crash", async () => {
    _routes = {
      "/admin/customers/": {
        data: {
          results: [
            customer(),
            customer({
              id: 2,
              name: "Youssef Alami",
              phone: "0655667788",
              phone_verified: false,
              email: "",
              wallet_balance: "0.00",
              loyalty_points: 0,
              is_driver: true,
            }),
          ],
          total: 2,
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
    expect(text).toContain("adminCustomers.title");
    // Loaded table branch (the column header renders only when customers.length && !loading
    // && !fetchError — i.e. the v-else data-views block ran).
    expect(text).toContain("adminCustomers.colCustomer");
    // Customer rows rendered from the fetched payload (own-template v-for, not a stubbed child).
    expect(text).toContain("Aicha Benali");
    expect(text).toContain("Youssef Alami");
  });
});
