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
 *   2. The page imports useRoute from vue-router (A-22 deep-link; mocked in the
 *      W3 block below) and renders NO <router-link>, so no RouterLink stub is needed.
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
  // Run 8 G3b W8 (A2-29): the page imports the shared extractor as a named
  // export. Test-double mirrors the detail-or-fallback contract the page
  // relies on (server detail when present, translated fallback otherwise).
  extractApiErrorMessage: (err, fallback) => err?.response?.data?.detail || fallback,
}));

import AdminCustomers from "../AdminCustomers.vue";
import api from "../../lib/api";
import { useConfirmModal } from "../../composables/useConfirmModal";

const mountPage = () =>
  shallowMount(AdminCustomers, {
    global: {
      stubs: {
        // The detail slide-over is a <Teleport>/<Transition> to body; render it
        // inline so wrapper.text()/find() can see it (mirrors AdminDrivers).
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

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

/**
 * MERGE NOTE (Run 8 G3a): append this describe block to
 * frontend/src/pages/__tests__/AdminCustomers.mount.test.js (after pulling it),
 * and add the api + useConfirmModal imports if the file lacks them:
 *   import api from "../../lib/api";
 *   import { useConfirmModal } from "../../composables/useConfirmModal";
 * The block assumes the file's existing _routes / mountCustomers / beforeEach
 * (localStorage.clear + real pinia + vi.clearAllMocks). It drives the detail
 * slide-over through wrapper.vm.openDetail (the row-click path is covered by the
 * file's existing smoke tests).
 *
 * Covers:
 *   A2-01 — Remove driver confirms first; PATCH is skipped on cancel.
 *   A2-03 — ledger shows "latest 50 of N" + per-row balance_after.
 *   A2-04 — orders show "latest 50 of N" from the backend count.
 *   A2-05 — cashout renders as outflow (red, −) with a real label; earning has one.
 */

const findButton = (wrapper, text) =>
  wrapper.findAll("button").find((b) => b.text().includes(text));

const detailPayload = (overrides = {}) => ({
  id: 5,
  name: "Sara",
  phone: "0611223344",
  phone_verified: true,
  email: "",
  email_verified: false,
  has_google: false,
  wallet_balance: "120.00",
  loyalty_points: 10,
  is_driver: false,
  is_driver_online: false,
  created_at: "2026-01-01T10:00:00Z",
  trust: { avg_score: null, count: 0 },
  delivery_jobs: 0,
  transactions_total: 2,
  transactions: [],
  ...overrides,
});

describe("AdminCustomers — driver toggle + ledger/orders caps + tx labels (A2-01/A2-03/A2-04/A2-05)", () => {
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

  const openDetailFor = async (detail, ordersPayload = { results: [], count: 0 }) => {
    _routes = {
      // Orders first: _match is substring-first-match, and the detail key
      // "/admin/customers/5/" would shadow "/admin/customers/5/orders/".
      "/admin/customers/5/orders/": { data: ordersPayload },
      "/admin/customers/5/": { data: detail },
    };
    wrapper = mountPage();
    await flushPromises();
    await wrapper.vm.openDetail({ id: 5, name: "Sara" });
    await flushPromises();
    return wrapper;
  };

  it("ledger shows the cap note and per-row balance_after (A2-03)", async () => {
    await openDetailFor(detailPayload({
      transactions_total: 73,
      transactions: [
        { id: 1, type: "topup", amount: "50.00", balance_after: "120.00", tenant_id: null, tenant_name: "", reference: "TOP-1", note: "", created_at: "2026-02-01T10:00:00Z" },
        { id: 2, type: "payment", amount: "20.00", balance_after: "70.00", tenant_id: null, tenant_name: "", reference: "ORD-1", note: "", created_at: "2026-02-02T10:00:00Z" },
      ],
    }));
    expect(wrapper.text()).toContain('adminCustomers.ledgerCapped({"shown":2,"total":73})');
    expect(wrapper.text()).toContain("120.00");
  });

  it("orders show the cap note from the backend count (A2-04)", async () => {
    await openDetailFor(detailPayload(), {
      results: [
        { order_number: "A1", restaurant: "Chez Test", status: "completed", fulfillment_type: "", total: "45.00", currency: "MAD", created_at: "2026-02-01T10:00:00Z" },
        { order_number: "A2", restaurant: "Chez Test", status: "completed", fulfillment_type: "", total: "30.00", currency: "MAD", created_at: "2026-02-02T10:00:00Z" },
      ],
      count: 120,
      scanned_restaurants: 1,
    });
    expect(wrapper.text()).toContain('adminCustomers.ordersCapped({"shown":2,"total":120})');
  });

  it("cashout renders as outflow with a real label; earning has a real label (A2-05)", async () => {
    await openDetailFor(detailPayload({
      transactions: [
        { id: 1, type: "cashout", amount: "100.00", balance_after: "20.00", tenant_id: null, tenant_name: "", reference: "CO-1", note: "", created_at: "2026-02-01T10:00:00Z" },
        { id: 2, type: "earning", amount: "45.00", balance_after: "120.00", tenant_id: null, tenant_name: "", reference: "JOB-1", note: "", created_at: "2026-02-02T10:00:00Z" },
      ],
    }));
    const text = wrapper.text();
    expect(text).toContain("customerAccount.walletTxCashout");
    expect(text).toContain("customerAccount.walletTxEarning");
    expect(text).not.toContain("customerAccount.walletTxFallback");
    // The cashout row is an outflow: red amount with a minus sign.
    expect(text).toContain("−");
  });

  it("Remove driver confirms first; cancelling skips the PATCH (A2-01)", async () => {
    await openDetailFor(detailPayload({ is_driver: true, delivery_jobs: 3 }));
    await findButton(wrapper, "adminCustomers.removeDriver").trigger("click");
    const { _settle } = useConfirmModal();
    _settle(false);
    await flushPromises();
    expect(api.patch).not.toHaveBeenCalled();

    api.patch.mockResolvedValue({ data: { id: 5, is_driver: false, is_driver_online: false, reopened_deliveries: 2 } });
    await findButton(wrapper, "adminCustomers.removeDriver").trigger("click");
    _settle(true);
    await flushPromises();
    expect(api.patch).toHaveBeenCalledWith("/admin/customers/5/", { is_driver: false });
  });
});

/**
 * MERGE NOTE (Run 8 G3b, W3): append this describe block to
 * frontend/src/pages/__tests__/AdminCustomers.mount.test.js.
 * The page now imports `useRoute` from vue-router (A-22 deep-link), so this
 * block adds a vue-router mock. vi.mock is hoisted, so it applies file-wide:
 * the base smoke tests above get query {} (no auto-open) and are unaffected.
 * The mock factory only reads `_routeQuery` from lazy closures (call time),
 * the same TDZ-safe pattern as the file's existing `_routes` matcher.
 * NOTE for the coordinator: the file header comment ("imports NOTHING from
 * vue-router") is stale after this change — update it at merge time.
 *
 * Covers:
 *   A-22 — ?customer=<id> auto-opens that customer's detail slide-over
 *           (row from the loaded list); no/invalid query opens nothing.
 */
let _routeQuery = {};
vi.mock("vue-router", () => ({
  useRoute: () => ({ query: _routeQuery }),
}));

describe("AdminCustomers — ?customer deep-link auto-open (A-22)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    _routeQuery = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    _routeQuery = {};
  });

  // Key order matters: _match is substring-first-match, and the list key
  // "/admin/customers/" is a substring of the detail/orders URLs, so it goes last.
  const mountWithQuery = async (query, detailOverrides = {}) => {
    _routeQuery = query;
    _routes = {
      "/admin/customers/5/orders/": { data: { results: [], count: 0 } },
      "/admin/customers/5/": { data: detailPayload({ id: 5, name: "Sara", ...detailOverrides }) },
      "/admin/customers/": {
        data: { results: [customer({ id: 5, name: "Sara" })], total: 1 },
      },
    };
    wrapper = mountPage();
    await flushPromises();
    await flushPromises();
    return wrapper;
  };

  it("?customer=5 auto-opens the detail slide-over for the listed customer", async () => {
    await mountWithQuery({ customer: "5" });
    expect(api.get).toHaveBeenCalledWith("/admin/customers/5/");
    const text = wrapper.text();
    expect(text).toContain("adminCustomers.detailKicker");
    expect(text).toContain("Sara");
    expect(text).toContain("120.00"); // detail wallet tile from the detail payload
  });

  it("no query param opens nothing (plain list mount)", async () => {
    await mountWithQuery({});
    expect(wrapper.text()).not.toContain("adminCustomers.detailKicker");
    const detailCalls = api.get.mock.calls.filter(([url]) => url === "/admin/customers/5/");
    expect(detailCalls).toHaveLength(0);
  });

  it("invalid ?customer value opens nothing and fetches no detail", async () => {
    await mountWithQuery({ customer: "abc" });
    expect(wrapper.text()).not.toContain("adminCustomers.detailKicker");
    const detailCalls = api.get.mock.calls.filter(([url]) => url.includes("/admin/customers/abc"));
    expect(detailCalls).toHaveLength(0);
  });
});
/**
 * Run 8 G3b W8 — appended describe (base tests above untouched).
 * Reuses the file's module-level helpers: mountPage, _routes, customer,
 * detailPayload, findButton, api, useConfirmModal.
 *
 * Covers:
 *   A2-15 — unknown order status renders orderStatus.statusUnknown (never
 *            "Pending"); scheduled maps to statusScheduled.
 *   A2-29 — credit above the 100,000 server cap is blocked client-side
 *            (no confirm, no POST); a credit failure with no server detail
 *            shows the translated creditFailed fallback via
 *            extractApiErrorMessage.
 *   A2-30 — ledger rows render the per-row balance_after label (already in
 *            the base page; locked in here so it cannot regress silently).
 *   A2-31 — suspend confirms first then PATCHes { is_suspended: true };
 *            cancelling skips the PATCH; profile edit PATCHes name/phone/
 *            email; suspended customers show a chip on the list.
 */
describe("AdminCustomers — Run 8 G3b W8 (A2-15/A2-29/A2-30/A2-31)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // clearAllMocks drops call history, not implementations — re-assert the
    // default resolve so a mockResolvedValue set by an earlier test cannot leak.
    api.patch.mockResolvedValue({ data: {} });
    api.post.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  const openDetailFor = async (detail, ordersPayload = { results: [], count: 0 }) => {
    _routes = {
      // Orders first: _match is substring-first-match, and the detail key
      // "/admin/customers/5/" would shadow "/admin/customers/5/orders/".
      "/admin/customers/5/orders/": { data: ordersPayload },
      "/admin/customers/5/": { data: detail },
      // List LAST: "/admin/customers/" is a substring of every detail URL, so it
      // must not shadow them. STAGING FIX (G3b W8): the detail opens for the REAL
      // list row, not a fresh literal — saveProfile updates detail.* + syncRow(),
      // and the panel header renders selected.name; with a literal, selected never
      // sees the save and the header keeps the old name ("Sara" vs "Sara New").
      "/admin/customers/": {
        data: { results: [customer({ id: 5, name: "Sara" })], total: 1 },
      },
    };
    wrapper = mountPage();
    await flushPromises();
    await wrapper.vm.openDetail(wrapper.vm.customers[0]);
    await flushPromises();
    return wrapper;
  };

  it("A2-15: unknown order status renders Unknown, never Pending", async () => {
    await openDetailFor(detailPayload(), {
      results: [
        { order_number: "X1", restaurant: "Chez Test", status: "refunded_later", fulfillment_type: "", total: "10.00", currency: "MAD", created_at: "2026-02-01T10:00:00Z" },
      ],
      count: 1,
      scanned_restaurants: 1,
    });
    const text = wrapper.text();
    expect(text).toContain("orderStatus.statusUnknown");
    expect(text).not.toContain("orderStatus.statusPending");
  });

  it("A2-15: scheduled order status maps to its own label", async () => {
    await openDetailFor(detailPayload(), {
      results: [
        { order_number: "X2", restaurant: "Chez Test", status: "scheduled", fulfillment_type: "", total: "10.00", currency: "MAD", created_at: "2026-02-01T10:00:00Z" },
      ],
      count: 1,
      scanned_restaurants: 1,
    });
    expect(wrapper.text()).toContain("orderStatus.statusScheduled");
  });

  it("A2-29: credit above 100000 is blocked client-side — no confirm, no POST", async () => {
    await openDetailFor(detailPayload());
    await wrapper.find('input[aria-label="adminCustomers.creditAmount"]').setValue("150000");
    await findButton(wrapper, "adminCustomers.creditBtn").trigger("click");
    await flushPromises();
    expect(api.post).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("adminCustomers.creditMax");
  });

  it("A2-29: credit failure with no server detail shows the translated fallback", async () => {
    await openDetailFor(detailPayload());
    api.post.mockRejectedValueOnce({});
    await wrapper.find('input[aria-label="adminCustomers.creditAmount"]').setValue("10");
    await findButton(wrapper, "adminCustomers.creditBtn").trigger("click");
    const { _settle } = useConfirmModal();
    _settle(true);
    await flushPromises();
    expect(api.post).toHaveBeenCalled();
    expect(wrapper.text()).toContain("adminCustomers.creditFailed");
  });

  it("A2-30: ledger rows render the per-row balance_after label", async () => {
    await openDetailFor(detailPayload({
      transactions: [
        { id: 1, type: "topup", amount: "50.00", balance_after: "120.00", tenant_id: null, tenant_name: "", reference: "TOP-1", note: "", created_at: "2026-02-01T10:00:00Z" },
      ],
    }));
    const text = wrapper.text();
    expect(text).toContain("adminCustomers.balanceAfter");
    expect(text).toContain("120.00");
  });

  it("A2-31: suspend confirms first, then PATCHes is_suspended true; button flips", async () => {
    api.patch.mockResolvedValue({ data: { id: 5, is_driver: false, is_driver_online: false, is_suspended: true, reopened_deliveries: 0 } });
    await openDetailFor(detailPayload({ is_suspended: false }));
    await findButton(wrapper, "adminCustomers.suspend").trigger("click");
    const { _settle } = useConfirmModal();
    _settle(true);
    await flushPromises();
    expect(api.patch).toHaveBeenCalledWith("/admin/customers/5/", { is_suspended: true });
    expect(wrapper.text()).toContain("adminCustomers.reactivate");
    expect(wrapper.text()).toContain("adminCustomers.suspended");
  });

  it("A2-31: suspend cancelled at the confirm skips the PATCH", async () => {
    await openDetailFor(detailPayload({ is_suspended: false }));
    await findButton(wrapper, "adminCustomers.suspend").trigger("click");
    const { _settle } = useConfirmModal();
    _settle(false);
    await flushPromises();
    expect(api.patch).not.toHaveBeenCalled();
  });

  it("A2-31: profile edit PATCHes name/phone/email", async () => {
    api.patch.mockResolvedValue({ data: { id: 5, name: "Sara New", phone: "0611223344", email: "", is_driver: false, is_driver_online: false, is_suspended: false, reopened_deliveries: 0 } });
    await openDetailFor(detailPayload());
    await findButton(wrapper, "common.edit").trigger("click");
    await wrapper.find('input[aria-label="adminCustomers.editName"]').setValue("Sara New");
    await findButton(wrapper, "common.save").trigger("click");
    await flushPromises();
    expect(api.patch).toHaveBeenCalledWith("/admin/customers/5/", { name: "Sara New", phone: "0611223344", email: "" });
    expect(wrapper.text()).toContain("Sara New");
  });

  it("A2-31: suspended customers show a chip on the list", async () => {
    _routes = {
      "/admin/customers/": {
        data: { results: [customer({ is_suspended: true })], total: 1 },
      },
    };
    wrapper = mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain("adminCustomers.suspended");
  });
});
