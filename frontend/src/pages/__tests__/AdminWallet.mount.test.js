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

import api from "../../lib/api";
import adminApi from "../../lib/adminApi";
import { useConfirmModal } from "../../composables/useConfirmModal";
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

const findButton = (wrapper, text) =>
  wrapper.findAll("button").find((b) => b.text().includes(text));

const findButtons = (wrapper, text) =>
  wrapper.findAll("button").filter((b) => b.text() === text);

const voucher = (overrides = {}) => ({
  id: 1,
  code: "ABCD-1234",
  amount: "50.00",
  note: "",
  is_used: false,
  is_revoked: false,
  used_by_name: null,
  used_at: null,
  expires_at: null,
  created_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

describe("AdminWallet — vouchers + settings load (A-19/A-20/A-21)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // Re-apply the default URL-routed implementations (a test below overrides
    // adminApi.get; clearAllMocks does not restore implementations).
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    adminApi.get.mockImplementation((url) => Promise.resolve(_match(url)));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  const mountWithVouchers = async (vouchers) => {
    _routes = { "/admin/wallet/vouchers/": { data: { vouchers } } };
    wrapper = mountWallet();
    await flushPromises();
    return wrapper;
  };

  // A-20: an expired-unused voucher no longer shows the green "Active" pill, and
  // a revoked voucher shows "Revoked" with no Revoke button.
  it("voucher rows show Expired / Revoked / Active states (no fake Active)", async () => {
    await mountWithVouchers([
      voucher({ id: 1, code: "EXP-1", expires_at: "2020-01-01T00:00:00Z" }),
      voucher({ id: 2, code: "REV-1", is_revoked: true }),
      voucher({ id: 3, code: "ACT-1", expires_at: "2030-01-01T00:00:00Z" }),
    ]);
    const text = wrapper.text();
    expect(text).toContain("adminWallet.voucherExpired");
    expect(text).toContain("adminWallet.voucherRevoked");
    expect(text).toContain("adminWallet.voucherActive");
    // Revoke is offered for the expired + active vouchers, not the revoked one.
    expect(findButtons(wrapper, "adminWallet.voucherRevoke")).toHaveLength(2);
  });

  // A-20: Revoke confirms, POSTs to the revoke endpoint, flips the row.
  it("revoke posts to the revoke endpoint and flips the row to Revoked", async () => {
    await mountWithVouchers([voucher({ id: 7, code: "ACT-1", expires_at: "2030-01-01T00:00:00Z" })]);
    api.post.mockResolvedValue({ data: { id: 7, code: "ACT-1", is_revoked: true } });
    await findButtons(wrapper, "adminWallet.voucherRevoke")[0].trigger("click");
    const { _settle } = useConfirmModal();
    _settle(true);
    await flushPromises();
    expect(api.post).toHaveBeenCalledWith("/admin/wallet/vouchers/7/revoke/", {});
    expect(wrapper.text()).toContain("adminWallet.voucherRevoked");
    expect(findButtons(wrapper, "adminWallet.voucherRevoke")).toHaveLength(0);
  });

  // A-21: a past expiry is rejected client-side before the confirm modal / API.
  it("past voucher expiry is rejected without calling the API", async () => {
    await mountWithVouchers([]);
    wrapper.vm.voucherAmount = "20";
    wrapper.vm.voucherExpiry = "2020-01-01T10:00";
    await findButton(wrapper, "adminWallet.voucherGenerate").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("adminWallet.voucherExpiryPast");
    expect(api.post).not.toHaveBeenCalled();
  });

  // A-19: a failed settings load surfaces an inline error + retry (not a blank field).
  it("settings load failure shows an inline error with a working retry", async () => {
    adminApi.get.mockImplementation((url) =>
      url.includes("/admin/settings/")
        ? Promise.reject(new Error("settings down"))
        : Promise.resolve(_match(url)),
    );
    wrapper = mountWallet();
    await flushPromises();
    expect(wrapper.text()).toContain("adminWallet.settingsLoadFailed");
    expect(findButton(wrapper, "common.retry")).toBeTruthy();

    // Restore success and retry — the banner clears.
    adminApi.get.mockImplementation((url) => Promise.resolve(_match(url)));
    _routes["/admin/settings/"] = { data: { wallet_charge_approval_threshold: "500.00" } };
    await findButton(wrapper, "common.retry").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("adminWallet.settingsLoadFailed");
  });
});

/**
 * MERGE NOTE (Run 8 G3b, W3): append this describe block to
 * frontend/src/pages/__tests__/AdminWallet.mount.test.js.
 * Assumes the file's existing URL-routed api/adminApi mocks + mocked useI18n
 * (keys render as `ns.key` / `ns.key({json})`) and the real Pinia toast store.
 * The RouterLink stub mirrors AdminConsole.mount.test.js (same shape, same
 * comment): the page renders <router-link> via the app's global registration,
 * so no vue-router module mock is needed — only this stub in global.stubs.
 *
 * Covers:
 *   A-22 — wallet rows link to the admin-customers detail deep-link.
 *   A-23 — mobile card list mirrors the table rows (name + balance + actions).
 *   A-24 — voucher qty clamping shows a notice; the POST carries the clamped count.
 *   A-25 — copy-all-codes toasts an error on clipboard failure (and still
 *           shows Copied on success).
 *   A-26 — showZero toggle resets page = 1 before refetching.
 *   A-27 — fund-tenant dropdown shows the "first 200" note at 200 tenants.
 */
import { useToastStore } from "../../stores/toast";

const RouterLinkStub = { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" };

const mountWalletWithRouter = () =>
  shallowMount(AdminWallet, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  });

describe("AdminWallet — wallet P2s (A-22/A-23/A-24/A-25/A-26/A-27)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    // Re-apply the default URL-routed implementations (earlier describes override
    // api.post / adminApi.get; clearAllMocks does not restore implementations).
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    adminApi.get.mockImplementation((url) => Promise.resolve(_match(url)));
    api.post.mockImplementation(() => Promise.resolve({ data: {} }));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    // The A-25 tests assign a clipboard mock onto navigator; drop it so later
    // tests (here or in the same file) see jsdom's default again.
    try {
      delete navigator.clipboard;
    } catch {
      /* non-configurable in this jsdom — leave it; each A-25 test re-assigns */
    }
  });

  const mountWithWallets = async (customers, total) => {
    _routes = {
      "/admin/wallets/": { data: { results: customers, total: total ?? customers.length } },
    };
    wrapper = mountWalletWithRouter();
    await flushPromises();
    return wrapper;
  };

  const walletCustomer = (overrides = {}) => ({
    id: 42,
    name: "Aicha Benali",
    phone: "0611223344",
    wallet_balance: "125.50",
    ...overrides,
  });

  // A-22 + A-23: one Details deep-link per row in the table AND in the mobile
  // cards; the card list renders the same name + balance as the table.
  it("wallet rows link to the customer detail (table + mobile cards)", async () => {
    await mountWithWallets([
      walletCustomer(),
      walletCustomer({ id: 43, name: "Youssef Alami", email: "y@example.com", wallet_balance: "0.00" }),
    ]);
    const links = wrapper.findAllComponents({ name: "RouterLink" });
    expect(links).toHaveLength(4); // 2 table rows + 2 mobile cards
    expect(links[0].props("to")).toEqual({ name: "admin-customers", query: { customer: 42 } });
    expect(links[1].props("to")).toEqual({ name: "admin-customers", query: { customer: 43 } });
    expect(links[2].props("to")).toEqual({ name: "admin-customers", query: { customer: 42 } });

    const cards = wrapper.findAll("ul").find((u) => u.classes().includes("md:hidden"));
    expect(cards.exists()).toBe(true);
    expect(cards.text()).toContain("Aicha Benali");
    expect(cards.text()).toContain("125.50");
    expect(cards.text()).toContain("Youssef Alami");
    // The name renders twice: once in the table row, once in the mobile card.
    expect((wrapper.text().match(/Aicha Benali/g) || []).length).toBe(2);
  });

  // A-24: qty 60 clamps to 50 with a visible notice, and the POST mints 50.
  it("voucher qty above 50 shows a clamp notice and mints 50", async () => {
    _routes = { "/admin/wallet/vouchers/": { data: { vouchers: [] } } };
    wrapper = mountWalletWithRouter();
    await flushPromises();
    wrapper.vm.voucherAmount = "20";
    wrapper.vm.voucherQty = 60;
    await findButton(wrapper, "adminWallet.voucherGenerate").trigger("click");
    // The notice is set before the confirm modal resolves.
    expect(wrapper.text()).toContain('adminWallet.voucherQtyClamped({"requested":60,"count":50})');
    const { _settle } = useConfirmModal();
    _settle(true);
    await flushPromises();
    expect(api.post).toHaveBeenCalledWith(
      "/admin/wallet/vouchers/",
      expect.objectContaining({ count: 50 }),
    );
    // A successful batch clears the notice along with the qty.
    expect(wrapper.text()).not.toContain("adminWallet.voucherQtyClamped");
  });

  // A-24 (no-clamp path): an in-range qty shows no notice and mints as asked.
  it("voucher qty inside 1-50 shows no clamp notice", async () => {
    _routes = { "/admin/wallet/vouchers/": { data: { vouchers: [] } } };
    wrapper = mountWalletWithRouter();
    await flushPromises();
    wrapper.vm.voucherAmount = "20";
    wrapper.vm.voucherQty = 3;
    await findButton(wrapper, "adminWallet.voucherGenerate").trigger("click");
    expect(wrapper.text()).not.toContain("adminWallet.voucherQtyClamped");
    const { _settle } = useConfirmModal();
    _settle(true);
    await flushPromises();
    expect(api.post).toHaveBeenCalledWith(
      "/admin/wallet/vouchers/",
      expect.objectContaining({ count: 3 }),
    );
  });

  // A-25: clipboard denial toasts an error and leaves the button as Copy all.
  it("copy-all-codes failure toasts an error (no silent swallow)", async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    _routes = { "/admin/wallet/vouchers/": { data: { vouchers: [] } } };
    wrapper = mountWalletWithRouter();
    await flushPromises();
    wrapper.vm.generatedCodes = ["AAA-111", "BBB-222"];
    await flushPromises();
    const toast = useToastStore();
    const showSpy = vi.spyOn(toast, "show");
    await findButton(wrapper, "adminWallet.voucherCopyAll").trigger("click");
    await flushPromises();
    expect(showSpy).toHaveBeenCalledWith("adminWallet.voucherCopyFailed", "error");
    expect(wrapper.text()).toContain("adminWallet.voucherCopyAll");
    expect(wrapper.text()).not.toContain("adminWallet.voucherCopied");
  });

  // A-25 (success path, unchanged): a working clipboard still shows Copied.
  it("copy-all-codes success still shows Copied", async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    _routes = { "/admin/wallet/vouchers/": { data: { vouchers: [] } } };
    wrapper = mountWalletWithRouter();
    await flushPromises();
    wrapper.vm.generatedCodes = ["AAA-111", "BBB-222"];
    await flushPromises();
    await findButton(wrapper, "adminWallet.voucherCopyAll").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("adminWallet.voucherCopied");
  });

  // A-26: toggling showZero on page 3 refetches from page 1.
  it("showZero toggle resets the page to 1 before refetching", async () => {
    await mountWithWallets([walletCustomer()], 120);
    wrapper.vm.page = 3;
    await wrapper.find('input[type="checkbox"]').setValue(true);
    await flushPromises();
    expect(wrapper.vm.page).toBe(1);
    const walletCalls = api.get.mock.calls.filter(([url]) => url.includes("/admin/wallets/"));
    expect(walletCalls.length).toBeGreaterThanOrEqual(2);
    expect(walletCalls[walletCalls.length - 1][1].params.page).toBe(1);
  });

  // A-27: 200 tenants in the picker show the truncation note.
  it("fund-tenant picker shows the first-200 note at 200 tenants", async () => {
    const tenants = Array.from({ length: 200 }, (_, i) => ({
      id: i + 1,
      name: `Restaurant ${i + 1}`,
      float_balance: "0.00",
    }));
    _routes = { "/admin-tenants/": { data: { results: tenants } } };
    wrapper = mountWalletWithRouter();
    await flushPromises();
    expect(wrapper.text()).toContain("adminWallet.fundTenantsTruncated");
  });

  // A-27 (no-note path): a short tenant list shows no truncation note.
  it("fund-tenant picker shows no truncation note for a short list", async () => {
    _routes = {
      "/admin-tenants/": {
        data: { results: [{ id: 1, name: "Chez Test", float_balance: "10.00" }] },
      },
    };
    wrapper = mountWalletWithRouter();
    await flushPromises();
    expect(wrapper.text()).not.toContain("adminWallet.fundTenantsTruncated");
  });
});
