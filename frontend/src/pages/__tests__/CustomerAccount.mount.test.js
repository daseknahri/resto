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
import { describe, it, expect, vi, beforeEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

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
