/**
 * Mount smoke test for AdminWallet.vue (the platform-admin wallet page, ~712 lines).
 *
 * WHY: this is the app's recurring production bug class — a MONEY/admin page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup, an unguarded
 * browser API, a bad Intl currency call) throws inside <script setup> and was never caught
 * by a test. AdminWallet's setup() wires four composables/stores (useI18n / useConfirmModal /
 * useFocusTrap / useToastStore), builds `fmtBalance` (an Intl.NumberFormat currency:MAD over
 * currentLocale.value), and runs an onMounted that fires FOUR GETs across TWO axios
 * instances. shallowMount runs the page's OWN setup() + own template (the customer-wallets
 * table, the voucher/fund/settings sections, the bonus modal) while auto-stubbing the only
 * child (AppIcon), so any setup-time crash fails CI here instead of shipping a blank page.
 *
 * Pattern-faithful to pages/__tests__/AdminConsole.mount.test.js (URL-routed api mock + real
 * pinia + mocked useI18n), with the page-specific differences verified against the source:
 *   1. The api boundary is BOTH `lib/api` AND `lib/adminApi` (two separate axios instances).
 *      At mount: api.get('/admin/wallets/')  + api.get('/admin/wallet/vouchers/'),
 *                adminApi.get('/admin-tenants/') + adminApi.get('/admin/settings/').
 *      Both modules are mocked and both share one URL-routed matcher (URLs are globally
 *      distinct). Both expose get/post/put/patch/delete (the page uses api.get/post and
 *      adminApi.get/post/patch).
 *   2. The page imports NOTHING from vue-router (`grep "from 'vue-router'"` → no match) and
 *      renders NO <router-link> in its template — so there is no router module to mock and no
 *      RouterLink stub is needed.
 *
 * Left REAL (jsdom-safe, and none touched at mount):
 *   - the toast store (real Pinia).
 *   - useConfirmModal (module-level ref singletons; `confirm` only fires on a user click).
 *   - useFocusTrap (at setup it registers only a lazy `watch(bonusTarget)` + onBeforeUnmount;
 *     it adds a document 'keydown' listener ONLY when the modal opens — bonusTarget is null at
 *     mount, so nothing is bound). afterEach unmount tears down the watch + settles fetches.
 *   - newIdempotencyKey (only called from user-action handlers, never at mount).
 * The page registers NO interval / observer / WebSocket at mount (the two setTimeouts live in
 * onSearch/copyAllCodes, both user-triggered), so there is nothing timer-like to fake here.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in AdminWallet is { t, currentLocale } — the mock MUST return both or
// the setup destructure throws, and fmtBalance reads `currentLocale.value` as the locale arg
// of Intl.NumberFormat(currency:MAD). t echoes the key (params appended) so assertions can
// target the stable i18n keys the page's own template renders.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// One URL-routed matcher shared by BOTH mocked axios instances (lib/api + lib/adminApi). The
// four mount GETs default to `{ data: {} }` so the empty path renders; a test sets _routes to
// drive the loaded path. _routes/_match are module-level and referenced ONLY from the lazy
// vi.fn closures below (which run at CALL time, never in the hoisted factory body) → TDZ-safe.
// The two factories inline their object literal (no helper called at factory time) to mirror the
// proven AdminConsole.mount.test.js shape exactly. Both expose get/post/put/patch/delete since
// the page uses api.get/post and adminApi.get/post/patch.
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
vi.mock("../../lib/adminApi", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import AdminWallet from "../AdminWallet.vue";

const mountWallet = () => shallowMount(AdminWallet);

describe("AdminWallet — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // TRAP: the toast/other stores are localStorage-backed (staleCache); clear it FIRST so a
    // cache write in one test can't be served as still-"fresh" to the next.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Unmount settles the four in-flight mount fetches and tears down useFocusTrap's watch /
    // onBeforeUnmount so nothing leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) default mount: empty wallets/vouchers/tenants/settings ────────────
  // The core guard: the whole setup() (four composable/store wires, fmtBalance, the onMounted
  // Promise-fan of four GETs across two axios instances) and the whole own-template must render
  // with empty data and not throw. The H1 title is the always-rendered crash anchor; the empty
  // state confirms the customer-wallets fetch resolved down its empty branch.
  it("mounts with empty data (four mount GETs default-empty) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountWallet();
    }).not.toThrow();

    await flushPromises(); // onMounted → fetch / fetchTenants / fetchVouchers / fetchSettings

    expect(wrapper.exists()).toBe(true);
    // Header H1 (always rendered, page's own template) — the crash-guard anchor.
    expect(wrapper.text()).toContain("adminWallet.title");
    // Empty /admin/wallets/ (default { data: {} } → results falsy → customers.length 0) →
    // the wallets empty-state branch, confirming the money-table path resolved without throwing.
    expect(wrapper.text()).toContain("adminWallet.emptyTitle");
  });

  // ── (2) loaded mount: real customer wallets + a voucher record ────────────
  // Drives the page's OWN loaded money templates (not delegated to a stubbed child): the
  // customer-wallets v-for (fmtBalance currency render + the parseFloat(balance) > 0 "+" branch)
  // and the recent-vouchers list v-for (code + fmtBalance(amount) + is_used status label). These
  // are the array-render + Intl-currency paths that only run with non-empty string-amount payloads.
  it("mounts with a loaded wallets table + voucher list (string amounts) without a crash", async () => {
    _routes = {
      // customer wallet balances (string amounts, as the API ships them)
      "/admin/wallets/": {
        data: {
          results: [
            { id: 42, name: "Aicha Benali", phone: "0611223344", wallet_balance: "125.50" },
            { id: 43, name: "Youssef Alami", email: "y@example.com", wallet_balance: "0.00" },
          ],
          total: 2,
        },
      },
      // recent vouchers (string amount + used/active status) — the "transaction"-like records here
      "/admin/wallet/vouchers/": {
        data: {
          vouchers: [
            { code: "ABCD-1234", amount: "50.00", is_used: false },
            { code: "WXYZ-9876", amount: "20.00", is_used: true, used_by_name: "Sara" },
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountWallet();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Header still renders.
    expect(text).toContain("adminWallet.title");
    // Loaded wallets table branch (renders its column header only when customers.length && !loading).
    expect(text).toContain("adminWallet.colName");
    // Customer row rendered from the fetched payload (own-template v-for, not a stubbed child).
    expect(text).toContain("Aicha Benali");
    // Balance digits from fmtBalance (Intl currency:MAD, or its toFixed(2) fallback) — assert the
    // DIGITS, not the currency symbol/placement, which varies by ICU build.
    expect(text).toContain("125.50");
    // Voucher record rendered from its fetched payload (own-template list v-for + status label).
    expect(text).toContain("ABCD-1234");
  });
});
