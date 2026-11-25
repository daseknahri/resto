/**
 * Wave H targeted tests (2026-11-24): WALLET-1, WALLET-2 (frontend).
 * P2-2 backend: backend/tests/test_customer_topup_throttle.py.
 *
 * Two layers, as in Waves E/F/G:
 *   (1) i18n VALUE tests — import the real messages-en/fr/ar and assert the
 *       user-facing strings say the plain words. These lock the wording
 *       itself, which a mocked-t mount test cannot see.
 *   (2) Mount tests — mocked useI18n (t returns the key verbatim) + a
 *       URL-routed api mock + mocked customer/currency/tenant/cart/toast
 *       stores. They lock the structure: the return banner is actually
 *       visible (Wallet tab on ?topup=), the banner offers a balance
 *       re-check, and a slow webhook is caught by a delayed re-fetch.
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

// URL-routed api mock (same pattern as the Wave E/F/G mount tests).
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

// ── (1) i18n values ─────────────────────────────────────────────────────────
describe("Wave H — i18n values", () => {
  // WALLET-2: the success banner no longer claims completion from the
  // redirect param alone — it says the top-up is being confirmed.
  it("says the top-up is being confirmed, not processed (WALLET-2)", () => {
    expect(en.customerAccount.topUpSuccessMsg).toContain("confirming your top-up");
    expect(en.customerAccount.topUpSuccessMsg).not.toContain("processed");
    expect(en.customerAccount.topUpSuccessMsg).not.toContain("will reflect shortly");
    expect(fr.customerAccount.topUpSuccessMsg).toContain("confirmation de votre rechargement");
    expect(fr.customerAccount.topUpSuccessMsg).not.toContain("sera mis a jour sous peu");
    expect(ar.customerAccount.topUpSuccessMsg).toContain("جار تأكيد الشحن");
    // The cancelled copy is unchanged — cancelling needs no verification.
    expect(en.customerAccount.topUpCancelledMsg).toBe("Payment cancelled.");
  });

  // WALLET-2: the banner's check-balance action exists in every locale.
  it("offers a check-balance action in every locale (WALLET-2)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      expect(m.customerAccount.topUpCheckNow, `${name}.customerAccount.topUpCheckNow`).toBeTruthy();
    }
    expect(en.customerAccount.topUpCheckNow).toBe("Check balance now");
    expect(fr.customerAccount.topUpCheckNow).toBe("Verifier mon solde");
    expect(ar.customerAccount.topUpCheckNow).toBe("تحقق من رصيدك الآن");
  });

  // FR convention: new French values stay accent-free.
  it("keeps the new French values accent-free (FR file convention)", () => {
    const accented = /[àâäéèêëîïôöùûüç]/;
    expect(fr.customerAccount.topUpSuccessMsg).not.toMatch(accented);
    expect(fr.customerAccount.topUpCheckNow).not.toMatch(accented);
  });
});

// ── (2) CustomerAccount — top-up return (WALLET-1/2) ────────────────────────
describe("Wave H — CustomerAccount top-up return (WALLET-1/2)", () => {
  let wrapper;
  const walletGetCount = () =>
    api.get.mock.calls.filter((c) => String(c[0]).includes("/customer/wallet/")).length;

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

  it("lands on the Wallet tab on ?topup=success, banner visible (WALLET-1)", async () => {
    _query.topup = "success";
    await mountAccount();
    // The wallet panel (balance hero + PSP panel) renders, with the banner.
    expect(wrapper.text()).toContain("customerAccount.walletTitle");
    expect(wrapper.text()).toContain("customerAccount.topUpTitle");
    expect(wrapper.text()).toContain("customerAccount.topUpSuccessMsg");
    // The banner's refresh action is there.
    expect(wrapper.text()).toContain("customerAccount.topUpCheckNow");
    expect(walletGetCount()).toBeGreaterThanOrEqual(1);
  });

  it("lands on the Wallet tab on ?topup=cancelled, no refresh button (WALLET-1)", async () => {
    _query.topup = "cancelled";
    await mountAccount();
    expect(wrapper.text()).toContain("customerAccount.topUpTitle");
    expect(wrapper.text()).toContain("customerAccount.topUpCancelledMsg");
    // The re-check button is success-only.
    expect(wrapper.text()).not.toContain("customerAccount.topUpCheckNow");
  });

  it("lets an explicit ?tab= win over the top-up default (WALLET-1)", async () => {
    _query.tab = "orders";
    _query.topup = "success";
    await mountAccount();
    expect(wrapper.text()).not.toContain("customerAccount.topUpTitle");
    expect(wrapper.text()).not.toContain("customerAccount.topUpSuccessMsg");
  });

  it("stays on Overview with no top-up param (WALLET-1)", async () => {
    await mountAccount();
    expect(wrapper.text()).not.toContain("customerAccount.topUpTitle");
    expect(wrapper.text()).not.toContain("customerAccount.topUpSuccessMsg");
  });

  it("re-checks the balance when the banner button is tapped (WALLET-2)", async () => {
    _query.topup = "success";
    await mountAccount();
    const before = walletGetCount();
    const btn = wrapper.findAll("button").find((b) => b.text().includes("customerAccount.topUpCheckNow"));
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();
    expect(walletGetCount()).toBe(before + 1);
  });

  it("schedules one delayed balance re-check after a success return (WALLET-2)", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    _query.topup = "success";
    await mountAccount();
    const rechecks = setTimeoutSpy.mock.calls.filter((c) => c[1] === 6000);
    expect(rechecks).toHaveLength(1);
    const before = walletGetCount();
    await rechecks[0][0]();
    await flushPromises();
    expect(walletGetCount()).toBe(before + 1);
    setTimeoutSpy.mockRestore();
  });

  it("schedules no delayed re-check without a success return (WALLET-2)", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    await mountAccount();
    expect(setTimeoutSpy.mock.calls.filter((c) => c[1] === 6000)).toHaveLength(0);
    setTimeoutSpy.mockRestore();
  });
});
