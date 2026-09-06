/**
 * Mount smoke test for CustomerLayout.vue — the consumer chrome (~433 lines) that
 * WRAPS every customer/storefront route (customer-home, menu, cart, reserve,
 * customer-account, order-status …) with a persistent header, currency/language
 * switchers, notification bell, cart button, desktop nav + mobile bottom dock, a
 * closed/track-order banner, and the app-wide ChargeApprovalWatcher +
 * GlobalLiveStatusBar.
 *
 * WHY A LAYOUT TEST MATTERS MORE THAN A PAGE TEST: a setup()-time error here (a TDZ
 * ReferenceError, an undefined lookup, an unguarded browser API) white-screens the
 * ENTIRE customer section — every storefront route at once — not just one page. This
 * mounts the layout's real setup() + onMounted so any such crash fails CI here
 * instead of shipping a blank storefront (the recurring "untested page/layout
 * white-screens at setup()" bug class).
 *
 * VERIFIED SHAPE (read from the source, not assumed):
 *   - useI18n() is destructured as EXACTLY { currentLocale, t }. currentLocale is
 *     read as `currentLocale.value` inside a watch source (script L428), so the mock
 *     MUST return it ref-like ({ value: "en" }) or setup() throws on undefined.value.
 *   - Imports ONLY { useRoute } from vue-router. The template has NO $route/$router
 *     reads (grep-confirmed) — the route is consumed only via the script's useRoute()
 *     return — so NO global.mocks.$route is needed here (unlike AdminLayout /
 *     LandingLayout, whose templates read $route directly). RouterView (scoped-slot)
 *     + RouterLink are GLOBAL components → global.stubs.
 *   - useInstallPrompt() → destructured { canInstall: pwaCanInstall, install: pwaInstall }.
 *   - useCustomerPush() → destructured { autoRestore: pushAutoRestore, checkEnabled:
 *     pushCheckEnabled }. This composable touches the service worker / push
 *     subscription at module scope and via its methods, so it MUST be mocked. NOTE:
 *     onMounted calls `pushCheckEnabled().then(...)` (reached in the authenticated
 *     branch), so the mocked checkEnabled MUST return a Promise — a bare vi.fn()
 *     (→ undefined.then) would reject inside the fetchCustomer().then chain.
 *   - isRestaurantOpenNow (../lib/businessHours) + PLATFORM_NAME (../lib/brand) are
 *     pure — left REAL (isRestaurantOpenNow is only called on a non-null profile).
 *   - Stores are REAL pinia (cart / customer / currency / tenant). onMounted fires
 *     customerStore.fetchCustomer() (→ api.get, mocked), currencyStore.fetchRates()
 *     (→ global fetch, stubbed), applyColorScheme(), and news up a matchMedia listener.
 *   - Children (AppIcon, ChargeApprovalWatcher, CurrencySelector, GlobalLiveStatusBar,
 *     LanguageSwitcher, NotificationBell) are auto-stubbed by shallowMount.
 *
 * Pattern-faithful to layouts/__tests__/LandingLayout.mount.test.js (hoisted route
 * state, ref-returning composable mocks, setCustomer-for-loaded, RouterView slot
 * stub, guest vs authenticated cases) and pages/__tests__/Menu.mount.test.js
 * (matchMedia stub for the color-scheme branch; localStorage-first reset).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n: t echoes the key (params appended as JSON) so assertions target
// the EXACT keys the layout's OWN template renders. The layout destructures
// { currentLocale, t } — currentLocale MUST be ref-like ({ value }) because a watch
// source reads currentLocale.value (script L428); omitting it throws at setup().
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    currentLocale: { value: "en" },
  }),
}));

// onMounted → customerStore.fetchCustomer() → api.get('/customer/session/'). Default
// { data: {} } → data.customer is undefined → the store keeps customer=null (guest
// path). The authenticated test pre-seeds the store so this GET is a no-op.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// useInstallPrompt returns readonly refs { canInstall, installed, isStandalone, install };
// the layout destructures { canInstall: pwaCanInstall, install: pwaInstall } and the
// template reads pwaCanInstall in `v-if="pwaCanInstall"`. Return REAL refs (false) so
// template auto-unwrap works and the install button stays hidden — never firing a real
// beforeinstallprompt. (ref is dynamically imported inside the factory because vi.mock
// factories are hoisted above imports.)
vi.mock("../../composables/useInstallPrompt", async () => {
  const { ref } = await import("vue");
  return {
    useInstallPrompt: () => ({
      canInstall: ref(false),
      installed: ref(false),
      isStandalone: ref(false),
      install: vi.fn(),
    }),
  };
});

// useCustomerPush touches the service worker / push subscription — MUST be mocked so
// nothing real opens at mount. The layout destructures { autoRestore, checkEnabled }.
// checkEnabled MUST return a Promise: onMounted does `pushCheckEnabled().then(...)`
// (in the authenticated branch), so a bare vi.fn() would throw undefined.then inside
// the fetchCustomer().then chain. Resolve false → autoRestore is never reached.
vi.mock("../../composables/useCustomerPush", async () => {
  const { ref } = await import("vue");
  return {
    useCustomerPush: () => ({
      supported: ref(false),
      enabled: ref(false),
      permission: ref("default"),
      subscribed: ref(false),
      loading: ref(false),
      subscribe: vi.fn(),
      unsubscribe: vi.fn(),
      autoRestore: vi.fn(),
      checkEnabled: vi.fn(() => Promise.resolve(false)),
    }),
  };
});

// vue-router: the layout imports ONLY { useRoute }. useRouter is exported defensively
// (nothing in the load graph is known to call it at mount, but a transitively-imported
// stubbed child might). routeState is hoisted (referenced inside this factory, which is
// hoisted above imports) and reset per test. route.name/query/params drive the script's
// computeds (activeCustomerSection, navItems, trackBannerOrder) + the onMounted table sync.
const routeState = vi.hoisted(() => ({ name: "customer-home", path: "/", query: {}, params: {} }));
vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { useCustomerStore } from "../../stores/customer";
import CustomerLayout from "../CustomerLayout.vue";

// <RouterView> and <RouterLink> are GLOBAL (un-imported) components. The RouterView stub
// ignores the scoped slot, so the inner <Transition>/<component :is="Component"> never
// render — exactly what a chrome-only smoke test wants. The RouterLink stub renders its
// slot so nav / driver-switch text (e.g. roleSwitch.driverMode) is present in text().
const mountLayout = () =>
  shallowMount(CustomerLayout, {
    global: {
      stubs: {
        RouterView: { template: "<div data-test='page'></div>" },
        RouterLink: { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" },
      },
    },
  });

describe("CustomerLayout — mount smoke (customer chrome crash guard)", () => {
  let wrapper;

  beforeEach(() => {
    setActivePinia(createPinia());
    // localStorage FIRST: the currency/cart/tenant stores and the layout's own
    // color-scheme ('ui-color-scheme') + order-tracking ('lastOrderNumber') reads are
    // localStorage-backed, so a leaked write from a prior test would change what this
    // fresh mount sees.
    localStorage.clear();
    routeState.name = "customer-home";
    routeState.path = "/";
    routeState.query = {};
    routeState.params = {};
    vi.clearAllMocks();
    // jsdom has no matchMedia; the layout calls window.matchMedia UNCONDITIONALLY in
    // onMounted (_mqDark = window.matchMedia('(prefers-color-scheme: dark)') +
    // addEventListener('change', …)) and in the color-scheme ref init / applyColorScheme.
    // An unstubbed matchMedia would throw and crash the mount — stub it (jsdom-parity).
    vi.stubGlobal("matchMedia", (query) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent() {
        return false;
      },
    }));
    // currencyStore.fetchRates() (fired in onMounted) uses the GLOBAL fetch, not the
    // mocked api client. Stub it to a benign empty-rate response so no real network
    // request is attempted and the fallback-rates path stays clean (no console noise).
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) })));
  });

  afterEach(() => {
    // onUnmounted removes the matchMedia 'change' listener; unmounting keeps the
    // stubbed listener from leaking between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    vi.unstubAllGlobals();
  });

  // ── (1) guest / default render — the core setup()/onMounted crash guard ────────
  // setup() + onMounted (loadOrderTracking, syncTableFromQuery, fetchCustomer,
  // fetchRates, applyColorScheme, matchMedia listener) must not throw. Guest
  // (customer=null → isAuthenticated false) → the account nav badge and its
  // "Signed in" sr-only label are absent, and the authenticated-only driver switch
  // is absent.
  it("mounts for a guest without a setup() crash and renders the customer chrome", async () => {
    // The white-screen bug class throws synchronously inside setup()/onMounted, so
    // mount() itself would throw — this assertion is the guard.
    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);

    // Skip-link — the layout's own always-rendered a11y landmark.
    const skip = wrapper.find("a[href='#main-content']");
    expect(skip.exists()).toBe(true);
    expect(skip.text()).toBe("common.skipToMain");

    // Exactly ONE focusable <main id="main-content"> landmark (single-main pattern);
    // the RouterView stub renders the routed page inside it.
    const mains = wrapper.findAll("main");
    expect(mains).toHaveLength(1);
    expect(mains[0].attributes("id")).toBe("main-content");
    expect(mains[0].attributes("tabindex")).toBe("-1");
    expect(mains[0].find("[data-test='page']").exists()).toBe(true);

    const text = wrapper.text();
    // Guest → the account nav badge is empty → its "Signed in" label is NOT rendered.
    expect(text).not.toContain("customerLayout.signedIn");
    // No customer → the authenticated+driver "driver mode" switch is absent.
    expect(text).not.toContain("roleSwitch.driverMode");
  });

  // ── (2) authenticated customer with a driver dimension ─────────────────────────
  // Exercises the customer-session chrome: the account nav badge (●) renders its
  // "Signed in" sr-only label, and v-if="customerStore.customer?.is_driver" renders
  // the client⇄driver mode switch. setCustomer marks the store loaded, so onMounted's
  // fetchCustomer() short-circuits and does NOT overwrite the seeded customer with the
  // empty api mock (guards against a null-out race).
  it("mounts an authenticated driver customer and renders the authenticated chrome", async () => {
    useCustomerStore().setCustomer({ id: 1, name: "Sara", is_driver: true });

    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Same always-rendered chrome landmark.
    expect(text).toContain("common.skipToMain");
    // Authenticated → the account nav badge renders its "Signed in" sr-only label
    // (customerLayout.signedIn appears ONLY inside the v-if="item.badge" branch).
    expect(text).toContain("customerLayout.signedIn");
    // is_driver → the driver-mode switch renders (roleSwitch.driverMode appears ONLY
    // inside the customer?.is_driver branches — absent for a guest).
    expect(text).toContain("roleSwitch.driverMode");
  });
});
