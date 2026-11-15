/**
 * Mount smoke test for SuperAppHub.vue (the consumer super-app hub, ~472 lines).
 *
 * WHY: this big page had NO mount test. The app's recurring production bug class
 * is "a page white-screens on load because a setup()-time error (TDZ, undefined
 * map access, bad import) was never caught by a test". Mounting the page runs its
 * real setup() — so any such crash fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/MarketplaceMenuPage.mount.test.js:
 *   - shallowMount (the page pulls in heavy children: CustomerAuthModal, RoleSwitcher)
 *   - real pinia (setActivePinia(createPinia())) + a mocked lib/api
 *   - useI18n mocked to return deterministic keys
 *   - vue-router mocked (the page imports { RouterLink })
 *
 * The customer-activity + customer-push composables are intentionally left REAL:
 * they are best-effort and jsdom-safe (every fetch is try/caught, push is gated
 * behind unsupported navigator APIs), so running them exercises more real setup.
 * lib/services (getServices) is left REAL so the service-launcher v-for actually
 * indexes the page's ACCENT_CLASSES map for all six real accents — the classic
 * "undefined map key" crash path this guard exists to catch.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatNumber: (v) => String(v),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock: the hub fires several GETs on mount (session, activity,
// recent orders, businesses). Default: everything resolves empty so the guest
// path renders. Individual tests override _routes for the loaded/authenticated path.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// SuperAppHub imports { RouterLink } from 'vue-router' (static binding) AND uses a
// dynamic <component :is="'RouterLink'">. Export a RouterLink stub so the import
// binding is defined; the global stub covers the dynamic string resolution.
// vi.hoisted: the vi.mock('vue-router') factory below is hoisted above the imports
// and runs during import evaluation — before a plain `const` in the file body would
// initialize — so referencing a plain const there hits the TDZ ("0 test" collection
// error). vi.hoisted makes the stub available to the hoisted factory.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import api from "../../lib/api";
import { useCustomerStore } from "../../stores/customer";
import SuperAppHub from "../SuperAppHub.vue";

const mountHub = () =>
  shallowMount(SuperAppHub, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("SuperAppHub — mount smoke", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    _routes = {};
  });

  // ── (1) guest / default render ────────────────────────────────────────────
  // The whole point of the guard: setup() must not throw. The service-launcher
  // grid always renders (even for a guest), which exercises the ACCENT_CLASSES
  // map lookup over every real service accent.
  it("mounts for a guest without a setup() crash and renders the service grid", async () => {
    let wrapper;
    expect(() => {
      wrapper = mountHub();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Services section heading (sr-only) — present once the accent-mapped grid rendered.
    expect(wrapper.text()).toContain("home.verticalsTitle");
    // Guest: no personalized greeting / resume rail.
    expect(wrapper.text()).not.toContain("superAppHub.resumeTitle");
  });

  // ── (2) authenticated + resumable loaded state ────────────────────────────
  // Exercises the resume-rail cards (the RIDE_ACTIVE_LABEL map + the per-card
  // ACCENT_CLASSES lookup), "order again", and "my businesses" — the getter/map
  // paths that only run for a signed-in customer with activity.
  it("mounts an authenticated customer with active order + ride + package (resume rail)", async () => {
    // Pre-authenticate: setCustomer marks the store loaded, so the page's
    // onMounted fetchCustomer() short-circuits and the customer stays set.
    useCustomerStore().setCustomer({ id: 1, name: "Sara", phone: "0600000000" });

    _routes = {
      "/customer/active/": {
        data: {
          orders: [
            { order_number: "A123", restaurant_name: "Chez Test", restaurant_slug: "chez-test" },
          ],
          ride: { id: 7, status: "in_progress", dropoff_address: "12 Rue Test" },
          package: { id: 9, status: "searching", dropoff_address: "5 Ave Test" },
        },
      },
      "/customer/orders/all/": {
        data: {
          orders: [
            { order_number: "A122", restaurant_slug: "chez-test", restaurant_name: "Chez Test", status: "completed" },
          ],
        },
      },
      "/customer/businesses/": {
        data: {
          businesses: [
            { tenant_id: 1, restaurant_slug: "chez-test", restaurant_name: "Chez Test", order_count: 3, is_favorite: true },
          ],
        },
      },
    };

    let wrapper;
    expect(() => {
      wrapper = mountHub();
    }).not.toThrow();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Resume rail rendered (hasResumable true → resumeCards computed ran the map lookups).
    expect(wrapper.text()).toContain("superAppHub.resumeTitle");
    // "Order again" + "My businesses" rails rendered from their fetched payloads.
    expect(wrapper.text()).toContain("superAppHub.orderAgainTitle");
    expect(wrapper.text()).toContain("superAppHub.myBusinessesTitle");
  });

  // ── (3) authenticated but empty activity ──────────────────────────────────
  // Signed-in with nothing in flight: the resume/reorder rails must be absent and
  // setup must still not throw (the empty-state branch of every getter).
  it("mounts an authenticated customer with empty activity (no resume rail)", async () => {
    useCustomerStore().setCustomer({ id: 2, name: "Omar", phone: "0611111111" });
    // _routes empty → every fetch resolves { data: {} } → empty activity.

    let wrapper;
    expect(() => {
      wrapper = mountHub();
    }).not.toThrow();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).not.toContain("superAppHub.resumeTitle");
    expect(wrapper.text()).not.toContain("superAppHub.orderAgainTitle");
    // The service grid still renders for a signed-in customer.
    expect(wrapper.text()).toContain("home.verticalsTitle");
  });
});

const findButton = (wrapper, text) =>
  wrapper.findAll("button").find((b) => b.text().includes(text));

const deferred = () => {
  let resolve;
  const promise = new Promise((res) => { resolve = res; });
  return { promise, resolve };
};

describe("SuperAppHub — activity rails fail loudly + retry (A-28)", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
  });

  afterEach(() => {
    _routes = {};
  });

  const auth = () => useCustomerStore().setCustomer({ id: 1, name: "Sara", phone: "0600000000" });

  it("shows skeletons while activity loads, then the service grid", async () => {
    auth();
    const gate = deferred();
    api.get.mockImplementation((url) =>
      url.includes("/customer/active/") ? gate.promise : Promise.resolve(_match(url)),
    );
    const wrapper = mountHub();
    await flushPromises();
    // The active fetch is still pending → loading skeletons render, grid waits.
    expect(wrapper.findAll(".animate-pulse").length).toBeGreaterThan(0);
    expect(wrapper.text()).not.toContain("superAppHub.resumeTitle");

    gate.resolve({ data: { orders: [], ride: null, package: null } });
    await flushPromises();
    expect(wrapper.findAll(".animate-pulse").length).toBe(0);
    expect(wrapper.text()).toContain("home.verticalsTitle");
    wrapper.unmount();
  });

  it("failed resume + services sources show per-rail errors with a retry that clears them", async () => {
    auth();
    api.get.mockImplementation((url) => {
      if (url.includes("/customer/active/") || url.includes("/customer/services/")) {
        return Promise.reject(new Error("down"));
      }
      return Promise.resolve(_match(url));
    });
    const wrapper = mountHub();
    await flushPromises();

    expect(wrapper.text()).toContain("superAppHub.resumeLoadFailed");
    expect(wrapper.text()).toContain("superAppHub.servicesLoadFailed");
    // The resume rail itself is absent on failure — assert on its heading id,
    // not the title text: the error banner carries the same title as an sr-only
    // heading (a11y label), so the text is present in the error state by design.
    expect(wrapper.find("#resume-heading").exists()).toBe(false);

    // Retry with the sources healthy again — both banners clear.
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    await findButton(wrapper, "common.retry").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("superAppHub.resumeLoadFailed");
    expect(wrapper.text()).not.toContain("superAppHub.servicesLoadFailed");
    wrapper.unmount();
  });

  it("failed order-again + businesses sources show per-rail errors with retry", async () => {
    auth();
    api.get.mockImplementation((url) => {
      if (url.includes("/customer/orders/all/") || url.includes("/customer/businesses/")) {
        return Promise.reject(new Error("down"));
      }
      return Promise.resolve(_match(url));
    });
    const wrapper = mountHub();
    await flushPromises();

    expect(wrapper.text()).toContain("superAppHub.orderAgainLoadFailed");
    expect(wrapper.text()).toContain("superAppHub.businessesLoadFailed");
    // Same sr-only-heading note as the resume rail above: assert on the rail id.
    expect(wrapper.find("#reorder-heading").exists()).toBe(false);

    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    await findButton(wrapper, "common.retry").trigger("click");
    await flushPromises();
    expect(wrapper.text()).not.toContain("superAppHub.orderAgainLoadFailed");
    wrapper.unmount();
  });
});
