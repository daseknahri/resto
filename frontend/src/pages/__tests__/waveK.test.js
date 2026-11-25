/**
 * Wave K targeted tests (2026-11-25): flaw-audit fixes for the Wave H/I
 * wallet top-up work (F-01–F-13, N-01–N-03).
 * Backend: backend/tests/test_customer_topup_status.py.
 *
 * Two layers, as in Waves H/I:
 *   (1) i18n VALUE tests — import the real messages-en/fr/ar and assert the
 *       new strings say the plain words in every locale, FR accent-free,
 *       and the confirmed copy now uses the em dash (N-03).
 *   (2) Mount tests — mocked useI18n (t returns the key verbatim) + a
 *       URL-routed api mock + mocked customer/currency/tenant/cart/toast
 *       stores, same pattern as waveH/waveI.test.js. They lock the new
 *       behaviour: 12-poll cap + slow poll (F-04), poll-error backoff and
 *       give-up (F-02), terminal vs retryable "unknown" (F-03), unmount
 *       timer cleanup (F-13), banner visible with PSP off / phone
 *       unverified (F-06), awaiting-payment copy (F-05), failed copy
 *       (F-09), manual status re-check (F-10), intent 429 + cooldown
 *       (F-07), recent top-ups list (F-08).
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

// URL-routed api mock (same pattern as the Wave E/F/G/H/I mount tests).
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
describe("Wave K — i18n values", () => {
  // N-03: the confirmed copy now uses the em dash, like the success copy.
  it("uses the em dash in the confirmed copy, in every locale (N-03)", () => {
    expect(en.customerAccount.topUpConfirmedMsg).toBe(
      "Top-up confirmed — {amount} MAD added to your wallet."
    );
    expect(fr.customerAccount.topUpConfirmedMsg).toBe(
      "Rechargement confirme — {amount} MAD ajoutes a votre portefeuille."
    );
    expect(ar.customerAccount.topUpConfirmedMsg).toContain("—");
    expect(ar.customerAccount.topUpConfirmedMsg).toContain("{amount}");
  });

  // The new banner/action copy exists in every locale and says the plain words.
  it("has the new top-up copy in every locale (F-04/F-05/F-07/F-08/F-09)", () => {
    for (const [name, m] of [["en", en], ["fr", fr], ["ar", ar]]) {
      for (const k of [
        "topUpFailedMsg", "topUpStillConfirmingMsg", "topUpAwaitingPaymentMsg",
        "topUpTooManyAttemptsMsg", "topUpRecentTitle", "topUpStatusCreated",
        "topUpStatusCredited", "topUpStatusFailed",
      ]) {
        expect(m.customerAccount[k], `${name}.customerAccount.${k}`).toBeTruthy();
      }
    }
    expect(en.customerAccount.topUpFailedMsg).toContain("didn't go through");
    expect(en.customerAccount.topUpStillConfirmingMsg).toContain("Still confirming");
    expect(en.customerAccount.topUpAwaitingPaymentMsg).toContain("waiting for the money to land");
    expect(en.customerAccount.topUpTooManyAttemptsMsg).toContain("Too many attempts");
    expect(en.customerAccount.topUpRecentTitle).toBe("Recent top-ups");
    expect(en.customerAccount.topUpStatusCreated).toBe("Pending");
    expect(en.customerAccount.topUpStatusCredited).toBe("Confirmed");
    expect(en.customerAccount.topUpStatusFailed).toBe("Failed");
  });

  // FR convention: new French values stay accent-free.
  it("keeps the new French values accent-free (FR file convention)", () => {
    const accented = /[àâäéèêëîïôöùûüç]/;
    for (const k of [
      "topUpFailedMsg", "topUpStillConfirmingMsg", "topUpAwaitingPaymentMsg",
      "topUpTooManyAttemptsMsg", "topUpRecentTitle", "topUpStatusCreated",
      "topUpStatusCredited", "topUpStatusFailed", "topUpConfirmedMsg",
    ]) {
      expect(fr.customerAccount[k], k).not.toMatch(accented);
    }
  });
});

// ─── (2) CustomerAccount — Wave K poll/banner behaviour ─────────────────────
describe("Wave K — CustomerAccount top-up poll/banner fixes", () => {
  let wrapper;
  const walletGetCount = () =>
    api.get.mock.calls.filter((c) => String(c[0]).includes("/customer/wallet/")).length;
  const statusGetCount = () =>
    api.get.mock.calls.filter((c) => String(c[0]).includes("/customer/topup/status/")).length;
  const statusPollTimers = (spy) =>
    spy.mock.calls.filter((c) => c[1] === 5000);
  const slowPollTimers = (spy) =>
    spy.mock.calls.filter((c) => c[1] === 30000);

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
    // Restore the default api implementations (error/429 tests override them).
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    api.post.mockImplementation(() => Promise.resolve({ data: {} }));
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

  // Drive the latest 5000ms poll timer once (one more status GET).
  const driveOnePoll = async (setTimeoutSpy) => {
    const timers = statusPollTimers(setTimeoutSpy);
    expect(timers.length).toBeGreaterThan(0);
    await timers[timers.length - 1][0]();
    await flushPromises();
  };

  it("stops fast polling after 12 attempts, shows the still-confirming state, and keeps a slow 30s poll (F-04)", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    setStatus({ status: "pending", payment_status: "paid", balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(statusGetCount()).toBe(1);
    // 11 more timer-driven polls = 12 total.
    for (let i = 0; i < 11; i++) await driveOnePoll(setTimeoutSpy);
    expect(statusGetCount()).toBe(12);
    // No 13th fast poll — the loop switched to the slow background poll.
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(11);
    expect(slowPollTimers(setTimeoutSpy)).toHaveLength(1);
    expect(wrapper.text()).toContain("customerAccount.topUpStillConfirmingMsg");
    expect(wrapper.text()).not.toContain("customerAccount.topUpSuccessMsg");
    // The slow poll still runs: a webhook landing at 90s flips the banner.
    setStatus({ status: "confirmed", amount: "150.00", currency: "MAD", balance: "300.00" });
    const slow = slowPollTimers(setTimeoutSpy);
    await slow[slow.length - 1][0]();
    await flushPromises();
    expect(statusGetCount()).toBe(13);
    expect(wrapper.text()).toContain('customerAccount.topUpConfirmedMsg({"amount":"150.00"})');
    setTimeoutSpy.mockRestore();
  });

  it("retries transient poll errors with backoff and gives up after 3 consecutive failures (F-02)", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    api.get.mockImplementation((url) =>
      String(url).includes("/customer/topup/status/")
        ? Promise.reject(new Error("network down"))
        : Promise.resolve(_match(url)),
    );
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(statusGetCount()).toBe(1);
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(1);
    await driveOnePoll(setTimeoutSpy); // error 2
    expect(statusGetCount()).toBe(2);
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(2);
    await driveOnePoll(setTimeoutSpy); // error 3 — give up
    expect(statusGetCount()).toBe(3);
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(2);
    expect(wrapper.text()).toContain("customerAccount.topUpStillConfirmingMsg");
    setTimeoutSpy.mockRestore();
  });

  it("backs off 30s on a 429 poll error (F-02)", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    api.get.mockImplementation((url) =>
      String(url).includes("/customer/topup/status/")
        ? Promise.reject({ response: { status: 429 } })
        : Promise.resolve(_match(url)),
    );
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(statusGetCount()).toBe(1);
    expect(slowPollTimers(setTimeoutSpy)).toHaveLength(1);
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(0);
    setTimeoutSpy.mockRestore();
  });

  it("stops polling on a terminal unknown and shows the manual-check state (F-03)", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    setStatus({ status: "unknown", retryable: false, balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_nope";
    await mountAccount();
    expect(statusGetCount()).toBe(1);
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(0);
    expect(wrapper.text()).toContain("customerAccount.topUpStillConfirmingMsg");
    setTimeoutSpy.mockRestore();
  });

  it("keeps polling on a retryable unknown (F-03)", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    setStatus({ status: "unknown", retryable: true, balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(statusGetCount()).toBe(1);
    expect(statusPollTimers(setTimeoutSpy)).toHaveLength(1);
    expect(wrapper.text()).toContain("customerAccount.topUpSuccessMsg");
    setTimeoutSpy.mockRestore();
  });

  it("shows the awaiting-payment copy for pending + unpaid, and the confirming copy for pending + paid (F-05)", async () => {
    setStatus({ status: "pending", payment_status: "unpaid", balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    expect(wrapper.text()).toContain("customerAccount.topUpAwaitingPaymentMsg");
    expect(wrapper.text()).not.toContain("customerAccount.topUpSuccessMsg");
  });

  it("shows the failed copy on failed and stops polling (F-09)", async () => {
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

  it("manual check re-asks the status endpoint and flips the banner when the webhook landed (F-10)", async () => {
    setStatus({ status: "pending", payment_status: "paid", balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    const beforeStatus = statusGetCount();
    const beforeWallet = walletGetCount();
    // The webhook lands between the poll and the manual tap.
    setStatus({ status: "confirmed", amount: "150.00", currency: "MAD", balance: "300.00" });
    const btn = wrapper.findAll("button").find((b) => b.text().includes("customerAccount.topUpCheckNow"));
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();
    expect(statusGetCount()).toBe(beforeStatus + 1);
    expect(wrapper.text()).toContain('customerAccount.topUpConfirmedMsg({"amount":"150.00"})');
    expect(walletGetCount()).toBeGreaterThan(beforeWallet);
  });

  it("shows the return banner when the PSP flag is off and the phone is unverified (F-06)", async () => {
    _customer.platform.psp_topup_enabled = false;
    _customer.customer.phone_verified = false;
    _query.topup = "success";
    await mountAccount();
    // The banner is there even though the PSP panel (and its title) is not.
    expect(wrapper.text()).toContain("customerAccount.topUpSuccessMsg");
    expect(wrapper.text()).not.toContain("customerAccount.topUpTitle");
  });

  it("maps a 429 intent submit to the too-many-attempts copy and disables the submit for the cooldown (F-07)", async () => {
    api.post.mockImplementation((url) =>
      String(url).includes("/customer/topup/intent/")
        ? Promise.reject({ response: { status: 429 } })
        : Promise.resolve({ data: {} }),
    );
    _query.tab = "wallet";
    await mountAccount();
    const btn = wrapper.findAll("button").find((b) => b.text().includes("customerAccount.topUpBtn"));
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain("customerAccount.topUpTooManyAttemptsMsg");
    expect(wrapper.text()).not.toContain("customerAccount.topUpError");
    const after = wrapper.findAll("button").find((b) => b.text().includes("customerAccount.topUpBtn"));
    expect(after.attributes("disabled")).not.toBeUndefined();
  });

  it("lists recent top-ups on the Wallet tab (F-08)", async () => {
    _routes["/customer/topup/attempts/"] = {
      data: {
        attempts: [
          { session_id: "cs_1", amount: "100.00", currency: "MAD", status: "credited", created_at: "2026-11-25T10:00:00Z" },
          { session_id: "cs_2", amount: "50.00", currency: "MAD", status: "created", created_at: "2026-11-25T09:00:00Z" },
        ],
      },
    };
    _query.topup = "success";
    await mountAccount();
    expect(wrapper.text()).toContain("customerAccount.topUpRecentTitle");
    expect(wrapper.text()).toContain("customerAccount.topUpStatusCredited");
    expect(wrapper.text()).toContain("customerAccount.topUpStatusCreated");
    expect(wrapper.text()).toContain("100.00");
    expect(wrapper.text()).toContain("50.00");
  });

  it("clears the poll and re-check timers on unmount (F-13)", async () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");
    const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
    setStatus({ status: "pending", payment_status: "paid", balance: "150.00" });
    _query.topup = "success";
    _query.session_id = "cs_test_1";
    await mountAccount();
    // The mount schedules the 6000ms re-check and (after the first pending
    // poll) the 5000ms poll timer.
    const timerIds = setTimeoutSpy.mock.calls
      .map((c, i) => (c[1] === 5000 || c[1] === 6000 ? setTimeoutSpy.mock.results[i].value : null))
      .filter(Boolean);
    expect(timerIds.length).toBe(2);
    wrapper.unmount();
    wrapper = undefined;
    for (const id of timerIds) {
      expect(clearTimeoutSpy).toHaveBeenCalledWith(id);
    }
    setTimeoutSpy.mockRestore();
    clearTimeoutSpy.mockRestore();
  });
});
