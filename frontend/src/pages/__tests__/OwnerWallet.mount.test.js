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

describe("OwnerWallet — S1-I B-16 tenant currency", () => {
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
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // B-16: plan.currency is the SUBSCRIPTION-plan price currency and
  // profile.currency is never sent by the backend — neither may drive wallet
  // money. Seed both with hostile values; the MAD tenant default must win.
  // lib/intlFormatters is NOT mocked, so real Intl output discriminates:
  // MAD -> "MAD 842.50", USD -> "$842.50", EUR -> "€842.50".
  it("renders wallet money in MAD even when meta carries a USD plan currency and a EUR profile currency (B-16)", async () => {
    const { useTenantStore } = await import("../../stores/tenant");
    useTenantStore().meta = {
      plan: { currency: "USD" },
      profile: { currency: "EUR" },
    };
    _routes = {
      "/owner/wallet/float/": { data: { float_balance: "842.50" } },
    };

    wrapper = mountWallet();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("842.50");
    expect(wrapper.text()).toContain("MAD");
    expect(wrapper.text()).not.toContain("$");
    expect(wrapper.text()).not.toContain("€");
  });
});
// ── G4b-F (B-41) — appended by Run 8 G4b, cluster F ──────────────────────────
// Imports are hoisted, so these resolve to the same (mocked api / real
// useConfirmModal) modules as the imports at the top of the file.
import api from "../../lib/api";
import { useConfirmModal } from "../../composables/useConfirmModal";

describe("OwnerWallet — G4b-F (B-41 search cap / top-up confirm / amount)", () => {
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
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  const _customers = (n) =>
    Array.from({ length: n }, (_, i) => ({
      customer_id: i + 1,
      name: `Cust ${String(i + 1).padStart(2, "0")}`,
      phone: "0600000000",
      email: "",
      wallet_balance: "10.00",
    }));

  // Mount with one searchable customer selected, so the top-up form renders.
  const _mountSelected = async () => {
    routeState.query = { q: "sara" };
    _routes = {
      "/owner/customers/": {
        data: { customers: [{ customer_id: 5, name: "Sara K", phone: "0600000000", email: "", wallet_balance: "88.50" }] },
      },
      "/owner/wallet/history/5/": { data: { transactions: [] } },
    };
    wrapper = mountWallet();
    await flushPromises(); // drain fetchFloat + runSearch
    const resultBtn = wrapper.findAll("button").find((b) => b.text().includes("Sara K"));
    expect(resultBtn).toBeTruthy();
    await resultBtn.trigger("click");
    await flushPromises(); // drain fetchHistory
    expect(wrapper.text()).toContain("Sara K");
    return wrapper.find("#topup-amount");
  };

  // B-41: the search used to slice(0, 10) silently — matches 11+ were
  // unreachable with no note. The list now shows the first 10, a
  // "showing X of N" note, and a show-more button that reveals the rest.
  it("B-41: 12 matches show 10 + a more-results note, and show-more reveals all 12", async () => {
    routeState.query = { q: "cust" };
    _routes = {
      "/owner/customers/": { data: { customers: _customers(12) } },
    };

    wrapper = mountWallet();
    await flushPromises(); // drain fetchFloat + runSearch

    expect(wrapper.text()).toContain("Cust 01");
    expect(wrapper.text()).toContain("Cust 10");
    expect(wrapper.text()).not.toContain("Cust 11");
    expect(wrapper.text()).not.toContain("Cust 12");
    expect(wrapper.text()).toContain('ownerWallet.searchMoreResults({"shown":10,"total":12})');

    const showMore = wrapper
      .findAll("button")
      .find((b) => b.text() === "ownerWallet.searchShowMore");
    expect(showMore).toBeTruthy();
    await showMore.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Cust 11");
    expect(wrapper.text()).toContain("Cust 12");
    expect(wrapper.text()).not.toContain("ownerWallet.searchMoreResults");
  });

  // B-41: bare parseFloat accepted "10abc" as 10. Junk amounts must now be
  // rejected with an inline error and no POST. (The ref is set directly and a
  // tick awaited first — the FE-test lesson: never set a ref then immediately
  // click a :disabled-bound button.)
  it("B-41: junk top-up amounts (10abc / 10.005 / -5 / 0) are rejected, no POST", async () => {
    const amountInput = await _mountSelected();
    expect(amountInput.exists()).toBe(true);

    for (const junk of ["10abc", "10.005", "-5", "0"]) {
      wrapper.vm.topupAmount = junk;
      await wrapper.vm.$nextTick();
      const topupBtn = wrapper
        .findAll("button")
        .find((b) => b.text() === "ownerWallet.topupBtn");
      expect(topupBtn).toBeTruthy();
      await topupBtn.trigger("click");
      await flushPromises();
      expect(wrapper.text()).toContain("ownerWallet.amountInvalid");
    }
    expect(api.post).not.toHaveBeenCalledWith("/owner/wallet/topup/", expect.anything());
  });

  // B-41: a valid top-up confirms WITHOUT danger styling (money-in is not
  // destructive) and posts the strict 2dp amount only after approval.
  it("B-41: valid top-up confirms with danger:false and posts 25.50 after approval", async () => {
    const amountInput = await _mountSelected();
    await amountInput.setValue("25.50");

    const topupBtn = wrapper
      .findAll("button")
      .find((b) => b.text() === "ownerWallet.topupBtn");
    expect(topupBtn).toBeTruthy();
    await topupBtn.trigger("click");
    await flushPromises();

    // No POST before the owner approves the confirm dialog.
    expect(api.post).not.toHaveBeenCalledWith("/owner/wallet/topup/", expect.anything());
    expect(useConfirmModal().visible.value).toBe(true);
    expect(useConfirmModal().options.value.danger).toBe(false);

    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith(
      "/owner/wallet/topup/",
      expect.objectContaining({ customer_id: 5, amount: "25.50" })
    );
  });
});
