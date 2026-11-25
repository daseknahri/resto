/**
 * Wave I targeted tests (2026-11-24): WALLET-2 follow-up — the server-side
 * top-up-status endpoint, wired into the banner.
 * Backend: backend/tests/test_customer_topup_status.py.
 *
 * Two layers, as in Wave H:
 *   (1) i18n VALUE tests — import the real messages-en/fr/ar and assert the
 *       confirmed copy says the plain words in every locale.
 *   (2) Mount tests — mocked useI18n (t returns the key verbatim) + a
 *       URL-routed api mock + mocked customer/currency/tenant/cart/toast
 *       stores. They lock the structure: a success return WITH a session_id
 *       polls /customer/topup/status/, a "confirmed" flips the banner to the
 *       confirmed copy (with the credited amount) and re-fetches the wallet,
 *       and the poll stops on confirmed / failed / no session_id.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import en from "../../i18n/messages-en.js";
import fr from "../../i18n/messages-fr.js";
import ar from "../../i18n/messages-ar.js";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatDateTime: (v) => String(v),
    formatNumber: (v) => String(v),
    formatPrice: (v) => String(v),
    formatCurrency: (v) => String(v),
    itemCountLabel: (v) => `${v} items`,
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock (same pattern as the Wave E/F/G/H mount tests).
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    default: {
      get: vi.fn((url) => Promise.resolve(_match(url))),
      post: vi.fn(() => Promise.resolve({ data: {} })),
      patch: vi.fn(() => Promise.resolve({ data: {} })),
      put: vi.fn(() => Promise.resolve({ data: {} })),
      delete: vi.fn(() => Promise.resolve({ data: {} })),
    },
  };
});

vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({ confirm: vi.fn(() => Promise.resolve(false)) }),
}));

vi.mock("../../composables/useReorder", () => ({
  useReorder: () => ({ reorderFromOrder: vi.fn() }),
}));

vi.mock("../../composables/useCustomerPush", () => ({
  useCustomerPush: () => ({ checkEnabled: vi.fn() }),
}));

// Mutable route query, reset per test (hoisted so the vue-router mock can see it).
const _query = vi.hoisted(() => ({}));
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: _query }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const _customer = vi.hoisted(() => ({
  isAuthenticated: true,
  // The template shows a loading skeleton while !loaded — the real store
  // sets it after fetchCustomer(); the mock is already loaded.
  loaded: true,
  enabledVerticals: [],
  customer: {
    id: 1, name: "Test User", phone_verified: true, locale: "en",
    birthday: "", wallet_balance: 150,
  },
  platform: { psp_topup_enabled: true },
  fetchCustomer: vi.fn(async () => {}),
  setCustomer: vi.fn(),
}));
vi.mock("../../stores/customer", () => ({ useCustomerStore: () => _customer }));
vi.mock("../../stores/currency", () => ({
  useCurrencyStore: () => ({
    available: [{ code: "MAD", label: "MAD" }],
    selected: "MAD",
    setCode: vi.fn(),
  }),
}));
vi.mock("../../stores/tenant", () => ({
  useTenantStore: () => ({ resolvedMeta: { name: "Test Resto" } }),
}));
vi.mock("../../stores/cart", () => ({
  useCartStore: () => ({ items: [], recentOrders: [], clear: vi.fn() }),
}));
vi.mock("../../stores/toast", () => ({
  useToastStore: () => ({ show: vi.fn() }),
}));

import api from "../../lib/api";
import CustomerAccount from "../CustomerAccount.vue";

// ─── (1) i18n values ───────────────────────────────────────────────────────
describe("Wave I — i18n values", () => {
  // The confirmed copy says the credit landed, with the amount — in every
  // locale. It is the only copy the banner shows after the ledger confirms.
  it("says the top-up is confirmed with the amount, in every locale", () => {
    expect(en.customerAccount.topUpConfirmedMsg).toBe(
      "Top-up confirmed — {amount} MAD added to your wallet."
    );
    expect(fr.customerAccount.topUpConfirmedMsg).toBe(
      "Rechargement confirme — {amount} MAD ajoutes a votre portefeuille."
    );
    expect(ar.customerAccount.topUpConfirmedMsg).toBeTruthy();
    expect(ar.customerAccount.topUpConfirmedMsg).toContain("{amount}");
  });

  // FR convention: new French values stay accent-free.
  it("keeps the new French value accent-free (FR file convention)", () => {
    const accented = /[àâäéèêëîïôöùûüç]/;
    expect(fr.customerAccount.topUpConfirmedMsg).not.toMatch(accented);
  });
});

// ─── (2) CustomerAccount — status poll on the top-up return ────────────────
describe("Wave I — CustomerAccount top-up status poll", () => {
  let wrapper;
  const walletGetCount = () =>
    api.get.mock.calls.filter((c) => String(c[0]).includes("/customer/wallet/")).length;
  const statusGetCount = () =>
    api.get.mock.calls.filter((c) => String(c[0]).includes("/customer/topup/status/")).length;
  const statusPollTimers = (spy) =>
    spy.mock.calls.filter((c) => c[1] === 5000);

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {
      "/customer/wallet/": {
        data: {
          transactions: [], has_more: false, balance: 150,
          p2p_enabled: false, spend_by_vertical: {},
        },
      },
    };
    for (const k of Object.keys(_query)) delete _query[k];
    _customer.isAuthenticated = true;
    _customer.customer.phone_verified = true;
    _customer.platform.psp_topup_enabled = true;
    vi.clearAllMocks();
  });
  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    for (const k of Object.keys(_query)) delete _query[k];
  });

  const mountAccount = async () => {
    wrapper = shallowMount(CustomerAccount);
    await flushPromises();
    await wrapper.vm.$nextTick();
    return wrapper;
  };

  const setStatus = (data) => {
    _routes["/customer/topup/status/"] = { data };
  };

  it("polls the status endpoint on a success return WITH a session_id", async () => {
    setStatus({ status: "pending", payment_status: "unpaid", balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(statusGetCount()).toBe(1);
    expect(api.get.mock.calls.find((c) => String(c[0]).includes("/customer/topup/status/"))[0])
      .toContain("session_id=cs_test_1");
    // Pending + unpaid: the banner shows the awaiting-payment copy (Wave K F-05).
    expect(wrapper.text()).toContain("customerAccount.topUpAwaitingPaymentMsg");
    expect(wrapper.text()).not.toContain("customerAccount.topUpConfirmedMsg");
  });

  it("flips the banner to confirmed + re-fetches the wallet on confirmed", async () => {
    setStatus({ status: "confirmed", amount: "150.00", currency: "MAD", balance: "300.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(wrapper.text()).toContain('customerAccount.topUpConfirmedMsg({"amount":"150.00"})');
    expect(wrapper.text()).not.toContain("customerAccount.topUpSuccessMsg");
    // The manual re-check button hides once the credit is confirmed.
    expect(wrapper.text()).not.toContain("customerAccount.topUpCheckNow");
    expect(walletGetCount()).toBeGreaterThanOrEqual(2);
  });

  it("keeps polling while pending, then confirms on the next poll", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    setStatus({ status: "pending", payment_status: "unpaid", balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(statusGetCount()).toBe(1);
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(1);
    // The webhook lands between polls — the next poll confirms.
    setStatus({ status: "confirmed", amount: "150.00", currency: "MAD", balance: "300.00" });
    const before = walletGetCount();
    await statusPollTimers(setTimeoutSpy)[0][0]();
    await flushPromises();
    expect(statusGetCount()).toBe(2);
    expect(wrapper.text()).toContain('customerAccount.topUpConfirmedMsg({"amount":"150.00"})');
    expect(walletGetCount()).toBe(before + 1);
    // No further poll once confirmed.
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(1);
    setTimeoutSpy.mockRestore();
  });

  // Wave K F-09: on "failed" the banner switches to the payment-didn't-go-through copy.
  it("stops polling on failed and shows the failed copy", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    setStatus({ status: "failed", payment_status: "unpaid", balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(statusGetCount()).toBe(1);
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(0);
    expect(wrapper.text()).toContain("customerAccount.topUpFailedMsg");
    expect(wrapper.text()).not.toContain("customerAccount.topUpSuccessMsg");
    expect(wrapper.text()).not.toContain("customerAccount.topUpConfirmedMsg");
    setTimeoutSpy.mockRestore();
  });

  it("never polls without a session_id (fallback re-check only)", async () => {
    setStatus({ status: "confirmed", amount: "150.00", currency: "MAD", balance: "300.00" });
    _query.topup = "success";
    await mountAccount();
    expect(statusGetCount()).toBe(0);
    expect(wrapper.text()).toContain("customerAccount.topUpSuccessMsg");
  });

  it("never polls on a cancelled return", async () => {
    setStatus({ status: "confirmed", amount: "150.00", currency: "MAD", balance: "300.00" });
    _query.topup = "cancelled";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(statusGetCount()).toBe(0);
    expect(wrapper.text()).toContain("customerAccount.topUpCancelledMsg");
  });
});
