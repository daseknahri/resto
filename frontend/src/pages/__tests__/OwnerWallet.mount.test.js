/**
 * Mount smoke test for OwnerWallet.vue (the owner wallet / float / driver-cashout /
 * customer top-up page, ~611 lines). A MONEY surface.
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined map
 * access, bad import) was never caught by a test". Mounting the page runs its real
 * setup() + onMounted for real, so any such crash fails CI here instead of in
 * production — and this is a money page (restaurant float, driver cash-out,
 * customer wallet top-ups), so a silent white-screen here is especially costly.
 *
 * Pattern-faithful to pages/__tests__/OwnerBilling.mount.test.js +
 * pages/__tests__/OwnerHome.mount.test.js (URL-routed api mock):
 *   - shallowMount (auto-stubs the one child component, AppIcon) + real pinia
 *     (setActivePinia(createPinia())) + a mocked lib/api
 *   - useI18n mocked to return deterministic keys ({ t, currentLocale })
 *   - vue-router mocked (the page imports { useRoute } and reads route.query.q)
 *
 * Page-specific notes (verified by reading the source, not assumed):
 *   - useI18n destructure is `{ t, currentLocale }`. The page does NOT use
 *     formatCurrency/formatPrice — it formats money itself via Intl.NumberFormat in
 *     fmtBalance()/fmtDate(), keyed off currentLocale.value ("en" here) and the
 *     tenant currency (tenant.resolvedMeta?.plan?.currency, which is null in jsdom →
 *     falls back to 'MAD'). So the loaded assertions check DIGITS, never the
 *     currency-symbol string/placement.
 *   - It imports ONLY { useRoute } from vue-router (no RouterLink, no useRouter, and
 *     no <router-link> in the template). onMounted reads route.query.q, so the mock's
 *     useRoute exposes a mutable `routeState.query` a test can seed before mounting.
 *     useRouter is mocked defensively (unused by the page) for safety parity.
 *   - onMounted fires fetchFloat() → GET /owner/wallet/float/, and — only when
 *     route.query.q has length >= 2 — runSearch(q) → GET /owner/customers/. Default
 *     (empty query): just the float GET. Everything resolves empty by default so the
 *     fresh page renders.
 *   - The wallet transaction history (walletHistory) is gated behind `v-if="selected"`,
 *     and `selected` is only set by selectCustomer() — reached via a search-result
 *     click or a token resolve, NEVER from a bare mount. So test 2 drives the page's
 *     real primary flow: seed route.query.q → onMounted runs the customer search →
 *     click the rendered result → GET /owner/wallet/history/{id}/ → the transactions
 *     render. That exercises the page's own money template on real records: the float
 *     (fmtBalance), each searched customer's wallet_balance (fmtBalance), and each
 *     transaction's amount (fmtBalance) + note/type branch + fmtDate(created_at).
 *   - No intervals / poll / visibilitychange / WebSocket / observers at mount; the
 *     only lifecycle hook is onBeforeUnmount(stopScan), which is null-safe when never
 *     scanning. Camera scan (getUserMedia/BarcodeDetector) is user-action only.
 *   - useConfirmModal + the tenant/toast stores are left REAL: they are jsdom-safe
 *     (useConfirmModal is pure refs; confirm() is only called by doTopup, a user
 *     action) — matching the other mount-smoke tests.
 *   - localStorage.clear() in beforeEach: the REAL tenant store getters touch the
 *     staleCache-backed meta cache; clearing keeps tests isolated (hygiene parity
 *     with the sibling mount-smoke tests).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
    // Not used by OwnerWallet (it formats money via Intl itself) — provided
    // defensively so the mock matches the composable's fuller shape.
    formatNumber: (v) => String(v),
    formatCurrency: (v) => String(v),
  }),
}));

// URL-routed api mock. onMounted GETs /owner/wallet/float/ (always) and
// /owner/customers/ (only when route.query.q is seeded). A search-result click
// then GETs /owner/wallet/history/{id}/. Default: everything resolves empty so the
// fresh page renders; tests set _routes to drive the loaded/money path.
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

// OwnerWallet imports { useRoute } from 'vue-router' and reads route.query.q in
// onMounted. vi.hoisted: the vi.mock('vue-router') factory is hoisted above the
// imports and runs during import evaluation — referencing a plain `let` there would
// hit the TDZ ("0 test" collection error) — so the mutable query holder is hoisted.
// Tests seed routeState.query BEFORE mounting; useRoute captures it at setup time.
const routeState = vi.hoisted(() => ({ query: {}, params: {} }));
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: routeState.params, query: routeState.query }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OwnerWallet from "../OwnerWallet.vue";

const mountWallet = () =>
  shallowMount(OwnerWallet, {
    global: {
      stubs: {
        // The one <Transition> wrapper around the selected-customer top-up section;
        // render the slot directly so the selected state appears deterministically.
        Transition: { template: "<slot />" },
      },
    },
  });

describe("OwnerWallet — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    routeState.query = {};
    routeState.params = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No intervals/observers to leak, but unmount runs onBeforeUnmount(stopScan) and
    // keeps teardown clean — parity with the other mount-smoke tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) fresh mount: empty float, no search query ─────────────────────────────
  // The core guard: setup() + the async onMounted (fetchFloat) + the whole template
  // must render with empty data and not throw. With no route.query.q, no customer
  // search fires; the float GET resolves empty → floatBalance stays "0.00" → the
  // float card + all always-rendered sections render.
  it("mounts fresh (empty float / no query) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountWallet();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Header title (h1, always rendered) — the crash-guard anchor.
    expect(wrapper.text()).toContain("ownerWallet.title");
    // Float card + customer-search headings are always rendered too.
    expect(wrapper.text()).toContain("ownerWallet.floatTitle");
    expect(wrapper.text()).toContain("ownerWallet.searchTitle");
  });

  // ── (2) loaded money path: float + searched customer + wallet transactions ────
  // Drives the page's own money template on real records:
  //   - fetchFloat → the float amount (fmtBalance)
  //   - route.query.q → onMounted runSearch → a customer row with a wallet_balance
  //     (fmtBalance) + the .filter/.map mapping (customer_id → id)
  //   - clicking the rendered result → selectCustomer → fetchHistory → the
  //     transaction list (each tx's note/type branch, fmtDate(created_at), and the
  //     +/− amount via fmtBalance)
  // Assertions check DIGITS only, so they are robust to currency-symbol/locale
  // differences in Intl output.
  it("mounts loaded (float + customer + wallet transactions) and renders money without a crash", async () => {
    routeState.query = { q: "sara" }; // >= 2 chars → onMounted runs the customer search
    _routes = {
      "/owner/wallet/float/": { data: { float_balance: "842.50" } },
      "/owner/customers/": {
        data: {
          customers: [
            { customer_id: 5, name: "Sara K", phone: "0600000000", email: "", wallet_balance: "88.50" },
          ],
        },
      },
      "/owner/wallet/history/5/": {
        data: {
          transactions: [
            { id: 1, type: "topup", amount: "50.00", note: "Cash top-up", created_at: "2026-09-01T10:00:00Z", status: "completed" },
            { id: 2, type: "payment", amount: "12.25", note: "", created_at: "2026-09-02T12:30:00Z", status: "completed" },
          ],
        },
      },
    };

    expect(() => {
      wrapper = mountWallet();
    }).not.toThrow();

    await flushPromises(); // drain fetchFloat + runSearch
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("ownerWallet.title");
    // Float money rendered from the page's own fmtBalance (digits only).
    expect(wrapper.text()).toContain("842.50");
    // Search rail rendered a real customer row (mapping + fmtBalance ran).
    expect(wrapper.text()).toContain("Sara K");
    expect(wrapper.text()).toContain("88.50");

    // Select the searched customer → loads + renders the wallet transaction history.
    // Find the result button by its own text (robust to aria-attr rendering quirks).
    const resultBtn = wrapper.findAll("button").find((b) => b.text().includes("Sara K"));
    expect(resultBtn).toBeTruthy();
    await resultBtn.trigger("click");
    await flushPromises(); // drain fetchHistory

    // Transactions rendered: the note label (note || type) + the amount digits
    // (fmtBalance) — a transaction label AND balance formatting from the page's own
    // template, the loaded money assertion.
    expect(wrapper.text()).toContain("Cash top-up");
    expect(wrapper.text()).toContain("50.00");
    expect(wrapper.text()).toContain("12.25");
  });
});
