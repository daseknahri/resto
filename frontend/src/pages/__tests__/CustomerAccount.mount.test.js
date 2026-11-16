/**
 * Mount smoke test for CustomerAccount.vue (~2690 lines).
 *
 * WHY: this is the app's recurring production bug class — a big page white-screens
 * because a setup()-time error (a TDZ ReferenceError, an undefined lookup-map, a
 * bad import) throws inside <script setup> and was never caught by a test. This
 * page runs a heavy setup(): five stores, three composables, a large watch, and an
 * onMounted fetch fan-out. shallowMount runs the page's OWN setup() (the thing
 * under test) while auto-stubbing the child components (CustomerAccountOrders /
 * Profile / Reservations / Reviews / CustomerAuthModal), so any setup-time crash
 * fails CI here instead of shipping a blank page.
 *
 * Mocks are deliberately minimal — only useI18n, lib/api and vue-router. The leaf
 * composables (useReorder / useConfirmModal / useCustomerPush) are left real so the
 * smoke test also exercises their setup-time integration; they are jsdom-safe
 * (guarded navigator/Notification checks) and consume the mocked api/useI18n.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { nextTick } from "vue";
import { useCustomerStore } from "../../stores/customer";

// TRAP #1: any stub referenced inside a vi.mock factory must be vi.hoisted. vi.mock
// is hoisted above the imports and its factory runs during import evaluation —
// BEFORE a plain module-scope `const` initializes — so a plain const would hit the
// TDZ ("Cannot access before initialization") and the file collects 0 tests.
const RouterLinkStub = vi.hoisted(() => ({
  name: "RouterLink",
  props: ["to"],
  template: "<a><slot /></a>",
}));

// URL-routed api mock. `routes.current` is a per-test override table keyed by a
// substring of the request URL; anything unmatched resolves { data: {} }. Hoisted
// so the factory and the tests share one object. Reading it inside `respond`
// (called lazily from the vi.fn, not at factory-eval time) is TDZ-safe.
const routes = vi.hoisted(() => ({ current: {} }));

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    // Return the key verbatim (with params appended) so assertions can target the
    // stable i18n keys the page's own template renders.
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatPrice: (v) => String(v),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

vi.mock("../../lib/api", () => {
  const respond = (url = "") => {
    const table = routes.current || {};
    for (const key of Object.keys(table)) {
      if (url.includes(key)) return Promise.resolve(table[key]);
    }
    return Promise.resolve({ data: {} });
  };
  return {
    default: {
      get: vi.fn((url) => respond(url)),
      post: vi.fn(() => Promise.resolve({ data: {} })),
      patch: vi.fn(() => Promise.resolve({ data: {} })),
      delete: vi.fn(() => Promise.resolve({ data: {} })),
      put: vi.fn(() => Promise.resolve({ data: {} })),
    },
    // C-06 contract double (S2-H): known code -> localized apiClient key, else fallback.
    extractApiErrorMessage: (err, fallback = "") => {
      const code = err?.response?.data?.code;
      const MAP = { email_taken: "apiClient.emailTaken", email_invalid: "apiClient.emailInvalid" };
      if (code && MAP[code]) return MAP[code];
      if (typeof code === "string" && (code.startsWith("loyalty_") || code.startsWith("schedule_"))) return `apiClient.${code}`;
      return fallback;
    },
  };
});

// CustomerAccount reads route.query at setup (topup banner + ?tab= deep-link),
// uses the router, and imports RouterLink from vue-router.
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import CustomerAccount from "../CustomerAccount.vue";

const mountPage = () =>
  shallowMount(CustomerAccount, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        // Built-ins are NOT auto-stubbed by shallowMount; the page always renders a
        // <Teleport>/<Transition> receipt modal shell (its inner content is v-if'd
        // off by default), so stub them to no-op passthroughs.
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("CustomerAccount — mount smoke", () => {
  beforeEach(() => {
    // TRAP #2: the tenant/customer/currency stores are localStorage-backed
    // (staleCache); clear it FIRST so a cache write in one test can't be served as
    // still-"fresh" to the next, starving it of its own api mock payload.
    localStorage.clear();
    setActivePinia(createPinia());
    routes.current = {};
    vi.clearAllMocks();
  });

  it("mounts without a setup() crash for a guest (empty session)", async () => {
    // Default /customer/session/ → { data: {} } → customer stays null → the
    // guest / sign-in branch of the template renders.
    let wrapper;
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises(); // onMounted → await fetchCustomer() resolves, loaded=true
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Own-template headings (the mocked t returns the key verbatim). These live in
    // the page's own sign-in hero, not inside a stubbed child.
    const text = wrapper.text();
    expect(text).toContain("customerAccount.title");
    expect(text).toContain("customerAccount.signIn");
  });

  it("mounts a signed-in customer and renders own-template order + overview state", async () => {
    routes.current = {
      "/customer/session/": {
        data: {
          customer: {
            id: 7,
            name: "Sara",
            phone: "0612345678",
            phone_verified: true,
            wallet_balance: "125.50",
            loyalty_points: 40,
          },
          platform: { enabled_verticals: ["food"], psp_topup_enabled: false },
        },
      },
      // fetchOrders() → GET /customer/orders/?page=1. One active + one completed
      // order exercises the always-visible live-order banner, the overview
      // re-order rail v-for, and the pending/submitted-reviews computeds.
      "/customer/orders/?page=": {
        data: {
          orders: [
            {
              order_number: "A1",
              status: "preparing",
              total: "50.00",
              currency: "MAD",
              created_at: "2026-01-01T10:00:00Z",
              estimated_ready_minutes: 20,
              items: [{ dish_name: "Pizza", qty: 1, subtotal: "50.00" }],
            },
            {
              order_number: "A2",
              status: "completed",
              total: "80.00",
              currency: "MAD",
              created_at: "2026-01-02T10:00:00Z",
              has_rating: false,
              items: [{ dish_name: "Burger", qty: 2, subtotal: "80.00" }],
            },
          ],
          has_more: false,
        },
      },
    };

    let wrapper;
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    // Two flushes: onMounted awaits fetchCustomer() first, THEN (once
    // isAuthenticated) fires the un-awaited fetchOrders()/fetchWallet()/… fan-out,
    // so the orders payload lands on a later microtask hop.
    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Signed-in hero renders the customer name (page's own template, not a child).
    expect(text).toContain("Sara");
    // Overview tab (the default active tab) renders own-template tab/stat labels
    // through the mocked t.
    expect(text).toContain("customerAccount.tabOverview");
  });
});

// ── S2-B: C-02 pay-code error state + C-08 top-up validation ─────────────────
// Appended by S2-B; the base mount-smoke describe above is untouched. These
// tests mount a signed-in, phone-verified customer, switch to the wallet tab
// (role="tab", label key customerAccount.tabWallet) and drive the page's own
// pay-code / top-up panels. The mocked `t` returns keys verbatim (params
// JSON-appended), so the new i18n keys are asserted by key. lib/escape is left
// REAL (repo convention, cf. CustomerLeadPage.mount.test.js): the unsafe-URL
// test below only passes if the component really routes the redirect through
// safeExternalUrl — a direct `window.location.href = data.url` would show no
// topUpError. NOTE: the valid-redirect test assigns window.location.href to a
// Stripe URL, which jsdom reports as "Not implemented: navigation" noise; the
// test still passes (jsdom never actually navigates).
const walletRoutes = () => ({
  "/customer/session/": {
    data: {
      customer: {
        id: 7,
        name: "Sara",
        phone: "0612345678",
        phone_verified: true,
        wallet_balance: "125.50",
        loyalty_points: 40,
      },
      platform: { enabled_verticals: ["food"], psp_topup_enabled: true },
    },
  },
  "/customer/orders/?page=": {
    data: { orders: [], has_more: false },
  },
});

const mountWallet = async () => {
  const wrapper = mountPage();
  // Two flushes, as in the base signed-in test: onMounted awaits
  // fetchCustomer() first, then the un-awaited fan-out settles.
  await flushPromises();
  await flushPromises();
  const walletTab = wrapper
    .findAll('button[role="tab"]')
    .find((b) => b.text().includes("customerAccount.tabWallet"));
  expect(walletTab.exists()).toBe(true);
  await walletTab.trigger("click");
  return wrapper;
};

const getApi = async () => (await import("../../lib/api")).default;

const topUpInput = (wrapper) =>
  wrapper.find('input[placeholder="customerAccount.topUpAmountHint"]');
const topUpButton = (wrapper) =>
  wrapper.findAll("button").find((b) => b.text().includes("customerAccount.topUpBtn"));
const topUpCalls = (api) =>
  api.post.mock.calls.filter(([url]) => String(url).includes("/customer/topup/intent/"));

describe("CustomerAccount — S2-B C-02 pay-code error state", () => {
  // S2-B isolation: the base describe's beforeEach does not run for these
  // describes -- without it there is no active Pinia (setup() throws) and
  // the localStorage-backed stores + api mocks leak state between tests.
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    routes.current = {};
    vi.clearAllMocks();
  });
  it("shows a retryable error instead of an endless spinner when the pay-token load fails", async () => {
    routes.current = walletRoutes();
    const api = await getApi();
    const wrapper = await mountWallet();

    // Fail ONLY the pay-token call: the mount fan-out has already settled, and
    // the rejection is consumed by the very next get (the toggle's refresh).
    api.get.mockRejectedValueOnce(new Error("pay-token down"));
    const getsBefore = api.get.mock.calls.length;
    const toggle = wrapper
      .findAll("button")
      .find((b) => b.text().includes("customerAccount.payCodeShow"));
    expect(toggle.exists()).toBe(true);
    await toggle.trigger("click");
    await flushPromises();
    await flushPromises();

    expect(api.get.mock.calls.length).toBe(getsBefore + 1);
    expect(wrapper.text()).toContain("customerAccount.payCodeError");
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    // No endless spinner: the loading status element is gone once the error shows.
    expect(wrapper.findAll('[role="status"]').length).toBe(0);

    // Retry: the error panel's own button re-attempts the load.
    api.get.mockRejectedValueOnce(new Error("pay-token still down"));
    const retry = wrapper.find('[role="alert"] button');
    expect(retry.exists()).toBe(true);
    await retry.trigger("click");
    await flushPromises();
    await flushPromises();
    expect(api.get.mock.calls.length).toBe(getsBefore + 2);
    expect(wrapper.text()).toContain("customerAccount.payCodeError");
  });
});

describe("CustomerAccount — S2-B C-08 wallet top-up validation", () => {
  // S2-B isolation: the base describe's beforeEach does not run for these
  // describes -- without it there is no active Pinia (setup() throws) and
  // the localStorage-backed stores + api mocks leak state between tests.
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    routes.current = {};
    vi.clearAllMocks();
  });
  it("blocks an amount below the 10 minimum client-side with a range error and no POST", async () => {
    routes.current = walletRoutes();
    const api = await getApi();
    const wrapper = await mountWallet();

    const input = topUpInput(wrapper);
    expect(input.exists()).toBe(true);
    await input.setValue(9);
    await topUpButton(wrapper).trigger("click");
    await flushPromises();

    expect(topUpCalls(api)).toHaveLength(0);
    expect(wrapper.text()).toContain('customerAccount.topUpAmountError({"min":10,"max":2000})');
  });

  it("blocks an amount above the 2000 maximum client-side with a range error and no POST", async () => {
    routes.current = walletRoutes();
    const api = await getApi();
    const wrapper = await mountWallet();

    await topUpInput(wrapper).setValue(2001);
    await topUpButton(wrapper).trigger("click");
    await flushPromises();

    expect(topUpCalls(api)).toHaveLength(0);
    expect(wrapper.text()).toContain('customerAccount.topUpAmountError({"min":10,"max":2000})');
  });

  it("blocks a non-numeric amount client-side with a range error and no POST", async () => {
    routes.current = walletRoutes();
    const api = await getApi();
    const wrapper = await mountWallet();

    // A number input sanitizes "abc" to "" in jsdom, so drive the ref directly
    // (then nextTick so the :disabled binding settles before clicking).
    wrapper.vm.topUpAmount = "abc";
    await wrapper.vm.$nextTick();
    await topUpButton(wrapper).trigger("click");
    await flushPromises();

    expect(topUpCalls(api)).toHaveLength(0);
    expect(wrapper.text()).toContain("customerAccount.topUpAmountError");
  });

  it("posts a valid amount (clearing a prior range error) and routes the Stripe redirect through safeExternalUrl", async () => {
    routes.current = walletRoutes();
    const api = await getApi();
    const wrapper = await mountWallet();
    const input = topUpInput(wrapper);

    // First an out-of-range amount: inline error, no POST.
    await input.setValue(9);
    await topUpButton(wrapper).trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("customerAccount.topUpAmountError");
    expect(topUpCalls(api)).toHaveLength(0);

    // Then a valid amount: the error clears and the intent POST goes out.
    // (Set the once-value AFTER mount: the mount fan-out must not consume it.)
    api.post.mockResolvedValueOnce({
      data: { enabled: true, url: "https://checkout.stripe.com/c/pay/test-session" },
    });
    await topUpInput(wrapper).setValue(250);
    await topUpButton(wrapper).trigger("click");
    await flushPromises();

    const calls = topUpCalls(api);
    expect(calls).toHaveLength(1);
    expect(calls[0][1]).toEqual({ amount: "250" });
    expect(wrapper.text()).not.toContain("customerAccount.topUpAmountError");
    expect(wrapper.text()).not.toContain("customerAccount.topUpError");
  });

  it("shows the generic top-up error when the redirect URL fails the external-URL check", async () => {
    routes.current = walletRoutes();
    const api = await getApi();
    const wrapper = await mountWallet();

    // (Set the once-value AFTER mount: the mount fan-out must not consume it.)
    api.post.mockResolvedValueOnce({ data: { enabled: true, url: "javascript:alert(1)" } });
    await topUpButton(wrapper).trigger("click");
    await flushPromises();

    expect(topUpCalls(api)).toHaveLength(1);
    expect(wrapper.text()).toContain("customerAccount.topUpError");
  });
});

describe("CustomerAccount — C-06 email save never surfaces raw backend detail", () => {
  let wrapper;

  // S2-B lesson: an appended describe needs its own isolation beforeEach —
  // the base describe's hook does not run for it.
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    routes.current = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountAuthed = async () => {
    wrapper = mountPage();
    await flushPromises();
    const cs = useCustomerStore();
    cs.customer = { name: "Sara", email: "sara@example.com", phone: "+212600000000" };
    cs.loaded = true;
    await nextTick();
    await flushPromises();
    // The profile only renders on the profile tab (default tab is overview),
    // so select it first — same pattern as mountWallet in the S2-B describes.
    const profileTab = wrapper
      .findAll('button[role="tab"]')
      .find((t) => t.text().includes("customerAccount.tabProfile"));
    expect(profileTab.exists()).toBe(true);
    await profileTab.trigger("click");
    await nextTick();
    return wrapper;
  };

  const profileStub = (wrapper) => wrapper.findComponent({ name: "CustomerAccountProfile" });

  const saveEmailWith = async (wrapper, patchError) => {
    const api = await getApi();
    api.patch.mockRejectedValueOnce(patchError);
    profileStub(wrapper).vm.$emit("open-email-input");
    await nextTick();
    profileStub(wrapper).vm.$emit("update-editable-email", "new@example.com");
    await nextTick();
    profileStub(wrapper).vm.$emit("save-email");
    await flushPromises();
    await nextTick();
  };

  it("shows the localized message for a known backend code, not the raw detail", async () => {
    await mountAuthed();
    await saveEmailWith(wrapper, {
      response: { data: { code: "email_taken", detail: "A user with this email already exists." } },
    });
    expect(profileStub(wrapper).props("emailError")).toBe("apiClient.emailTaken");
    expect(wrapper.text()).not.toContain("A user with this email already exists.");
  });

  it("shows the localized generic for an unmapped code, never the raw detail", async () => {
    await mountAuthed();
    await saveEmailWith(wrapper, {
      response: { data: { code: "something_new", detail: "Brand new backend wording." } },
    });
    expect(profileStub(wrapper).props("emailError")).toBe("customerAccount.emailSaveFailed");
    expect(wrapper.text()).not.toContain("Brand new backend wording.");
  });
});
