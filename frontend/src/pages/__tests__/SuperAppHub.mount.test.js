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
 * The customer-activity composable is intentionally left REAL: it is best-effort
 * and jsdom-safe (every fetch is try/caught), so running it exercises more real
 * setup. useCustomerPush is MOCKED (see the mock below): it freezes `supported`
 * to false at import time in jsdom, so the push banner could never render.
 * lib/services (getServices) is left REAL so the service-launcher v-for actually
 * indexes the page's ACCENT_CLASSES map for all six real accents — the classic
 * "undefined map key" crash path this guard exists to catch.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { ref } from "vue";

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

// useCustomerPush is mocked, not left real: it computes `supported` and the
// initial `permission` ONCE at module import (module-level consts), so in
// jsdom they freeze to false/'denied' before any test can stub the window
// globals — stubbing PushManager/Notification/serviceWorker before mount
// cannot turn the banner on. The A-30 tests exercise the BANNER logic
// (dismissal persistence + 7-day expiry), not the composable's feature
// detection, so the mock stands in for it. Default: unsupported (banner
// hidden), exactly like the real composable in jsdom — the base smoke +
// A-28 tests are unaffected. A-30 tests flip _pushState.supported on per
// test; the W4 beforeEach resets it.
const _pushState = vi.hoisted(() => ({
  supported: false,
  permission: "default",
  subscribed: false,
}));
vi.mock("../../composables/useCustomerPush", () => ({
  useCustomerPush: () => ({
    supported: _pushState.supported,
    permission: ref(_pushState.permission),
    subscribed: ref(_pushState.subscribed),
    loading: ref(false),
    subscribe: vi.fn(() => Promise.resolve()),
    unsubscribe: vi.fn(() => Promise.resolve()),
    autoRestore: vi.fn(() => Promise.resolve()),
    checkEnabled: vi.fn(() => Promise.resolve(false)),
  }),
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

// ── W4 P2 gaps (A-29…A-33) — appended 2026-11-15 ─────────────────────────────
import { getServices } from "../../lib/services";
import { useToastStore } from "../../stores/toast";

describe("SuperAppHub — W4 P2 gaps (A-29…A-33)", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
    api.get.mockImplementation((url) => Promise.resolve(_match(url)));
    window.localStorage.clear();
    _pushState.supported = false;
    _pushState.permission = "default";
    _pushState.subscribed = false;
  });

  afterEach(() => {
    _routes = {};
    window.localStorage.clear();
  });

  const auth = () => useCustomerStore().setCustomer({ id: 1, name: "Sara", phone: "0600000000" });

  const order = (n) => ({ order_number: n, restaurant_name: "Chez Test", restaurant_slug: "chez-test" });

  const activeRoutes = (orders) => ({
    "/customer/active/": {
      data: {
        orders,
        ride: { id: 7, status: "in_progress", dropoff_address: "12 Rue Test" },
        package: { id: 9, status: "searching", dropoff_address: "5 Ave Test" },
      },
    },
    "/customer/orders/all/": { data: { orders: [] } },
    "/customer/businesses/": { data: { businesses: [] } },
  });

  const businessesRoutes = (businesses) => ({
    "/customer/active/": { data: { orders: [], ride: null, package: null } },
    "/customer/orders/all/": { data: { orders: [] } },
    "/customer/businesses/": { data: { businesses } },
  });

  // ── A-29: exactly one link to customer-account in the hero ────────────────
  it("hero links to customer-account exactly once (no duplicate 'My account' button)", async () => {
    auth();
    const wrapper = mountHub();
    await flushPromises();

    expect(wrapper.text()).toContain("superAppHub.signInGreeting");
    expect(wrapper.text()).not.toContain("superAppHub.myAccount");
    const accountLinks = wrapper
      .findAllComponents(RouterLinkStub)
      .filter((c) => c.props("to")?.name === "customer-account");
    expect(accountLinks.length).toBe(1);
    wrapper.unmount();
  });

  // A-30: the banner renders only when the (mocked) useCustomerPush reports
  // push as supported — the A-30 tests flip _pushState.supported on per test.
  const dismissButton = (wrapper) => wrapper.find('button[aria-label="common.dismiss"]');

  // ── A-30: push-banner dismissal persists 7 days in localStorage ───────────
  it("dismissing the push banner persists it; a remount stays dismissed", async () => {
    _pushState.supported = true;
    auth();
    const wrapper = mountHub();
    await flushPromises();
    expect(dismissButton(wrapper).exists()).toBe(true);

    await dismissButton(wrapper).trigger("click");
    await flushPromises();
    expect(dismissButton(wrapper).exists()).toBe(false);

    const raw = window.localStorage.getItem("rostoy:push-banner-dismissed");
    expect(raw).not.toBeNull();
    expect(Number(raw)).toBeGreaterThan(Date.now() - 60_000);
    wrapper.unmount();

    // Fresh mount, same localStorage: the dismissal survives the remount.
    const wrapper2 = mountHub();
    await flushPromises();
    expect(dismissButton(wrapper2).exists()).toBe(false);
    wrapper2.unmount();
  });

  it("a fresh (unexpired) dismissal hides the banner on first mount", async () => {
    _pushState.supported = true;
    auth();
    window.localStorage.setItem("rostoy:push-banner-dismissed", String(Date.now()));
    const wrapper = mountHub();
    await flushPromises();
    expect(dismissButton(wrapper).exists()).toBe(false);
    wrapper.unmount();
  });

  it("an expired dismissal (older than 7 days) shows the banner again", async () => {
    _pushState.supported = true;
    auth();
    window.localStorage.setItem(
      "rostoy:push-banner-dismissed",
      String(Date.now() - 8 * 24 * 60 * 60 * 1000),
    );
    const wrapper = mountHub();
    await flushPromises();
    expect(dismissButton(wrapper).exists()).toBe(true);
    wrapper.unmount();
  });

  // ── A-31: no emoji anywhere; services carry AppIcon names ─────────────────
  it("renders no emoji on the hub (hero, rails, service grid, partner strip)", async () => {
    auth();
    _routes = {
      "/customer/active/": {
        data: {
          orders: [order("A123")],
          ride: { id: 7, status: "in_progress", dropoff_address: "12 Rue Test" },
          package: { id: 9, status: "searching", dropoff_address: "5 Ave Test" },
        },
      },
      "/customer/orders/all/": {
        data: {
          orders: [{ order_number: "A122", restaurant_slug: "chez-test", restaurant_name: "Chez Test", status: "completed" }],
        },
      },
      "/customer/businesses/": {
        data: {
          businesses: [{ tenant_id: 1, restaurant_slug: "chez-test", restaurant_name: "Chez Test", order_count: 3, is_favorite: true }],
        },
      },
    };
    const wrapper = mountHub();
    await flushPromises();
    for (const e of ["👤", "🔑", "🔔", "🍽", "🛍", "🚕", "💊", "📦", "🏍", "🏪"]) {
      expect(wrapper.text()).not.toContain(e);
    }
    wrapper.unmount();
  });

  it("lib/services exposes AppIcon names, not emoji", () => {
    expect(getServices().map((s) => s.icon)).toEqual(["food", "bag", "taxi", "pill", "package", "bike"]);
  });

  // ── A-32: resume rail caps at 3 with a "view all" link ────────────────────
  it("caps the resume rail at 3 cards and shows a 'view all' link when more exist", async () => {
    auth();
    _routes = activeRoutes([order("A123"), order("A124")]); // 2 orders + ride + package = 4 cards
    const wrapper = mountHub();
    await flushPromises();

    expect(wrapper.text()).toContain("superAppHub.resumeViewAll");
    const section = wrapper.find('section[aria-labelledby="resume-heading"]');
    expect(section.findAll("a").length).toBe(4); // 3 cards + the view-all link
    const viewAll = wrapper
      .findAllComponents(RouterLinkStub)
      .find((c) => c.text().includes("superAppHub.resumeViewAll"));
    expect(viewAll.props("to")).toEqual({ name: "customer-account" });
    wrapper.unmount();
  });

  it("shows no 'view all' link when the resume rail fits in 3 cards", async () => {
    auth();
    _routes = activeRoutes([order("A123")]); // 1 order + ride + package = 3 cards
    const wrapper = mountHub();
    await flushPromises();

    expect(wrapper.text()).not.toContain("superAppHub.resumeViewAll");
    const section = wrapper.find('section[aria-labelledby="resume-heading"]');
    expect(section.findAll("a").length).toBe(3);
    wrapper.unmount();
  });

  // ── A-33: follow toggle toasts an error on failure, state unchanged ───────
  it("toasts an error and leaves the toggle unchanged when unfollow fails", async () => {
    auth();
    _routes = businessesRoutes([
      { tenant_id: 1, restaurant_slug: "chez-test", restaurant_name: "Chez Test", order_count: 3, is_favorite: true },
    ]);
    const wrapper = mountHub();
    await flushPromises();

    const toast = useToastStore();
    const showSpy = vi.spyOn(toast, "show");
    api.delete.mockRejectedValueOnce(new Error("down"));
    const btn = wrapper.find('button[aria-label^="superAppHub.unfollowAria"]');
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();

    expect(showSpy).toHaveBeenCalledWith("superAppHub.followFailed", "error");
    // Toggle state unchanged: still the unfollow button, not the follow one.
    expect(wrapper.find('button[aria-label^="superAppHub.unfollowAria"]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("flips the toggle on success without an error toast", async () => {
    auth();
    _routes = businessesRoutes([
      { tenant_id: 1, restaurant_slug: "chez-test", restaurant_name: "Chez Test", order_count: 0, is_favorite: false },
    ]);
    const wrapper = mountHub();
    await flushPromises();

    const toast = useToastStore();
    const showSpy = vi.spyOn(toast, "show");
    const btn = wrapper.find('button[aria-label^="superAppHub.followAria"]');
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();

    expect(showSpy).not.toHaveBeenCalled();
    expect(wrapper.find('button[aria-label^="superAppHub.unfollowAria"]').exists()).toBe(true);
    wrapper.unmount();
  });
});
