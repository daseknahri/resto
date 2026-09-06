/**
 * Mount smoke test for LandingLayout.vue (the public marketing/landing chrome
 * wrapper, ~275 lines) — the layout every consumer-facing / marketing route
 * renders inside (hub, marketplace, account, ride, courier, legal, contact...).
 *
 * WHY: the app's recurring production bug class is "a page/layout white-screens
 * on load because a setup()-time error (TDZ, undefined access, unguarded browser
 * API) was never caught by a test". A LAYOUT crash is worse than a page crash: it
 * white-screens the ENTIRE public section, not one route. Mounting the layout runs
 * its real setup() + onMounted (customerStore.fetchCustomer()) so any such crash
 * fails CI here instead of in production.
 *
 * Pattern-faithful to layouts/__tests__/PlainLayout.test.js (RouterView stub) and
 * pages/__tests__/{Home,SuperAppHub}.mount.test.js (real pinia + mocked lib/api +
 * composable mocks + URL-agnostic api).
 *
 * LAYOUT-SPECIFIC NOTE ($route): the nav RouterLinks bind :data-active="$route.path
 * === '/'" and $route.query.tab (template lines ~26-29, ~107-125). Those expressions
 * are evaluated by THIS component's render (they build the props passed to the stub),
 * so a stubbed RouterLink does NOT spare us from needing $route — it must be supplied
 * as a global mock (the standard VTU pattern for router-injected globals). The script's
 * useRoute() return (route.name) separately drives isConsumerContext.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n: t echoes the key (the layout destructures ONLY { t }).
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

// onMounted → customerStore.fetchCustomer() → api.get('/customer/session/').
// Default { data: {} } → data.customer is undefined → the store keeps customer=null
// (the guest path). The authenticated test pre-seeds the store so this GET is a no-op.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// useInstallPrompt returns readonly refs { canInstall, isStandalone, install }; the
// layout destructures { canInstall, isStandalone, install: installApp } and the
// template reads canInstall/isStandalone in `v-if="canInstall && !isStandalone"`.
// Return REAL refs (false) so template auto-unwrap works and the install button
// stays hidden — never firing a real beforeinstallprompt. (ref is dynamically
// imported inside the factory because vi.mock factories are hoisted above imports.)
vi.mock("../../composables/useInstallPrompt", async () => {
  const { ref } = await import("vue");
  return {
    useInstallPrompt: () => ({
      canInstall: ref(false),
      isStandalone: ref(false),
      install: vi.fn(),
    }),
  };
});

// vue-router: the layout imports ONLY { useRouter, useRoute }. RouterView/RouterLink
// are GLOBAL components used in the template (not imported), so they are covered by
// global.stubs below — no vi.hoisted stub needed. route.name drives isConsumerContext;
// the hoisted routeState is seeded per test (beforeEach resets it) and is ALSO handed
// to global.mocks.$route so the template's $route.path/$route.query reads resolve.
const routeState = vi.hoisted(() => ({ path: "/", query: {}, params: {}, name: "super-app-hub" }));
vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn() }),
}));

import { useCustomerStore } from "../../stores/customer";
import LandingLayout from "../LandingLayout.vue";

const mountLayout = () =>
  shallowMount(LandingLayout, {
    global: {
      // $route is read directly in the template's RouterLink bindings
      // ($route.path / $route.query.tab); supply it as a global mock.
      mocks: { $route: routeState, $router: { push: vi.fn() } },
      stubs: {
        // The routed child is irrelevant here (we test the layout chrome). This
        // stub ignores the scoped slot, so the inner <Transition>/<component :is>
        // never render — exactly what we want for a chrome-only smoke test.
        RouterView: { template: "<div data-test='page'></div>" },
        // Render the slot so nav / CTA text (e.g. roleSwitch.driverMode) is present
        // in wrapper.text(); the rest of the RouterLink attrs fall through harmlessly.
        RouterLink: { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" },
      },
    },
  });

describe("LandingLayout — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    routeState.path = "/";
    routeState.query = {};
    routeState.params = {};
    routeState.name = "super-app-hub"; // consumer context → isConsumerContext true
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) guest / default render — the core setup()-crash guard ───────────────
  // setup() + onMounted must not throw. Guest (customer=null → isAuthenticated
  // false) in consumer context renders the customer sign-in CTA; the
  // authenticated-only driver switch is absent.
  it("mounts for a guest without a setup() crash and renders the sign-in CTA", async () => {
    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Stable own-template chrome key — the skip-link, always rendered.
    expect(text).toContain("common.skipToMain");
    // Guest + consumer context → the customer sign-in CTA branch renders.
    expect(text).toContain("common.signIn");
    // No customer → the authenticated+driver "driver mode" switch is absent.
    expect(text).not.toContain("roleSwitch.driverMode");
  });

  // ── (2) authenticated customer with a driver dimension ──────────────────────
  // Exercises the customer-session chrome: v-if="customerStore.isAuthenticated"
  // and v-if="customerStore.customer?.is_driver". setCustomer marks the store
  // loaded, so the onMounted fetchCustomer() short-circuits and does NOT overwrite
  // the seeded customer with the empty api mock (guards against a null-out race).
  it("mounts an authenticated driver customer and renders the driver-switch chrome", async () => {
    useCustomerStore().setCustomer({ id: 1, name: "Sara", is_driver: true });

    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    expect(text).toContain("common.skipToMain");
    // Authenticated + driver → the persistent client⇄driver switch renders
    // (roleSwitch.driverMode appears ONLY inside that authenticated branch).
    expect(text).toContain("roleSwitch.driverMode");
    // Authenticated consumer → no sign-in CTA (mutually exclusive with the guest state).
    expect(text).not.toContain("common.signIn");
  });
});
