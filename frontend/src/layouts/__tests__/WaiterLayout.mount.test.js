/**
 * Mount smoke test for WaiterLayout.vue — the waiter/staff chrome layout (~280 lines)
 * that WRAPS the whole waiter/staff section with a sticky top bar (tenant brand + role
 * badge, connectivity + offline-queue indicators, language switcher, dark/light toggle,
 * an owner-view link, sign-out), the live waiter-call bell banner, and the
 * <main id="main-content"> landmark that hosts <RouterView />.
 *
 * WHY A LAYOUT TEST MATTERS MORE THAN A PAGE TEST: a layout wraps EVERY waiter route, so
 * a setup()-time error here (a TDZ ReferenceError, an undefined lookup, an unguarded
 * browser API, a realtime/timer leak) white-screens the ENTIRE waiter section — not one
 * page. Mounting the layout runs its real setup() + onMounted (activateTheme →
 * waiter.setupConnectivityListeners → loadWaiterCalls → realtime.connect → 30s poll
 * interval → visibilitychange listener) so any such crash fails CI here instead of
 * shipping a blank waiter surface.
 *
 * REALTIME / TIMER / THEME BOUNDARIES — all MOCKED (the real ones open a live WebSocket,
 * schedule reconnect/poll timers, and mutate <html>; left real they leak past teardown
 * and fail the CI job — the Leaflet-class trap). Destructured surfaces verified against
 * the composable source:
 *   - useWaiterCalls() returns { pending, load, acknowledge, handleRealtime }; the layout
 *     destructures { pending: waiterCallsPending, load: loadWaiterCalls,
 *     acknowledge: acknowledgeWaiterCall, handleRealtime: _handleWaiterCallRealtime }.
 *     `pending` MUST be a real ref — the template reads `waiterCallsPending.length`.
 *     loadWaiterCalls() fires in onMounted; the stub makes it a no-op so no
 *     /owner/waiter-calls/ GET is issued.
 *   - useOwnerRealtime(cb) returns { connect, disconnect } (thin wrapper over
 *     useRealtimeChannel → wss://<host>/ws/owner/). The layout calls _waiterRealtime.
 *     connect() at mount and .disconnect() at unmount. Mocking the WRAPPER avoids the
 *     real socket entirely; the layout reads no other member (no connectionState).
 *   - useOwnerTheme() returns { theme, setTheme, toggleTheme, activate, deactivate }; the
 *     layout destructures { theme: ownerTheme, toggleTheme, activate: activateTheme,
 *     deactivate: deactivateTheme } and calls activateTheme() at mount / deactivateTheme()
 *     at unmount (both set/strip document.documentElement's data-owner-theme). Stubbed to
 *     no-ops so <html> is never themed by the test.
 *
 * STORES LEFT REAL (real pinia): session / tenant / waiter / toast. The only mount-time
 * store touch is waiter.setupConnectivityListeners() — with an EMPTY offlineQueue
 * (localStorage cleared first, so the store's _loadQueue() returns []) it merely adds
 * online/offline window listeners and does NOT flushQueue (no api). tenant.meta === null →
 * tenantName falls back to "Restaurant". waiter.queueLength defaults to 0 (queued chip
 * hidden via v-show) and waiter.isOnline defaults to navigator.onLine. A mocked lib/api
 * keeps every store path hermetic — nothing actually fetches at mount (loadWaiterCalls is
 * stubbed; fetchMeta / fetchOrders are never called by this layout).
 *
 * $route / $router: a grep of the template found NO $route / $router usage (unlike
 * AdminLayout / LandingLayout, whose nav bindings read $route directly). WaiterLayout
 * imports ONLY { useRouter } from vue-router and calls router.push exclusively inside
 * handleSignOut (fired on the sign-out button click), never at mount — so NO
 * global.mocks.$route is needed and the vue-router mock exports only useRouter.
 * <RouterView> / <RouterLink> are GLOBAL (un-imported) components → global.stubs.
 *
 * Pattern-faithful to layouts/__tests__/{AdminLayout,LandingLayout}.mount.test.js and
 * pages/__tests__/OwnerOrders.mount.test.js (shallowMount + real pinia + a mocked lib/api
 * + async-ref composable factories).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n: t echoes the key so assertions target the EXACT keys the layout's
// OWN template renders. WaiterLayout destructures EXACTLY { t }; params are ignored by
// the stub (only param-less keys are asserted).
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k }),
}));

// lib/api is pulled in transitively by the session / tenant / waiter stores; NONE of them
// actually fetch at mount here (loadWaiterCalls is stubbed; fetchMeta / fetchOrders are
// never called by this layout). Mock it defensively so importing the stores stays
// hermetic (no lingering real axios instance), mirroring the sibling layout tests.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// useWaiterCalls: a data/realtime boundary. `pending` must be a REAL ref (the template
// reads waiterCallsPending.length → 0 → the bell banner stays hidden); load/acknowledge/
// handleRealtime are stubbed so onMounted's loadWaiterCalls() is a no-op and no ack /
// realtime path fires. (ref is imported inside the async factory because vi.mock factories
// are hoisted above the top-level imports.)
vi.mock("../../composables/useWaiterCalls", async () => {
  const { ref } = await import("vue");
  return {
    useWaiterCalls: () => ({
      pending: ref([]),
      load: vi.fn(),
      acknowledge: vi.fn(),
      handleRealtime: vi.fn(() => Promise.resolve(false)),
    }),
  };
});

// useOwnerRealtime: a live-WebSocket boundary. Stub connect()/disconnect() to no-ops so
// the layout's onMounted connect / onUnmounted disconnect wiring is exercised without ever
// opening wss://<host>/ws/owner/. The layout reads no other member off the return.
vi.mock("../../composables/useOwnerRealtime", () => ({
  useOwnerRealtime: () => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
}));

// useOwnerTheme: mutates document.documentElement (data-owner-theme) on activate/
// deactivate. Return a REAL theme ref (template reads ownerTheme === 'dark') and no-op
// activate/toggle/deactivate so <html> is never themed by the test.
vi.mock("../../composables/useOwnerTheme", async () => {
  const { ref } = await import("vue");
  return {
    useOwnerTheme: () => ({
      theme: ref("light"),
      setTheme: vi.fn(),
      toggleTheme: vi.fn(),
      activate: vi.fn(),
      deactivate: vi.fn(),
    }),
  };
});

// vue-router: WaiterLayout imports ONLY { useRouter } and calls router.push exclusively
// inside handleSignOut (on button click), never at mount. Exporting just useRouter is safe
// here — nothing else in the load graph (stores → lib/api; LanguageSwitcher → vue + useI18n)
// imports from vue-router.
vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import WaiterLayout from "../WaiterLayout.vue";
import { useSessionStore } from "../../stores/session";

// <RouterView> and <RouterLink> are GLOBAL (un-imported) components normally registered by
// the router plugin; the plugin-less test app resolves them via these stubs (a no-op <a>
// pass-through for RouterLink that renders its slot so link text is asserted, a page marker
// for RouterView). Neither is referenced inside a vi.mock factory, so neither needs
// vi.hoisted. No $route global mock — the template reads no $route/$router (grep-verified).
const mountLayout = () =>
  shallowMount(WaiterLayout, {
    global: {
      stubs: {
        RouterView: { template: "<div data-test='page'>page</div>" },
        RouterLink: { props: ["to"], template: "<a><slot /></a>" },
      },
    },
  });

describe("WaiterLayout — mount smoke (waiter chrome crash guard)", () => {
  let wrapper;

  beforeEach(() => {
    // The waiter store seeds offlineQueue from localStorage at init (_loadQueue); clear it
    // FIRST so no stale queue leaks across tests AND so setupConnectivityListeners() finds
    // an empty queue and never flushes (proven-recipe hygiene for cache-backed stores).
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Unmount fires onUnmounted → deactivateTheme (stub) + waiter.teardownConnectivity
    // Listeners (removes the window online/offline listeners) + realtime.disconnect (stub) +
    // clearInterval(30s poll) + removeEventListener(visibilitychange), so nothing leaks.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) default mount: the whole waiter chrome renders ─────────────────────
  // The core guard: the entire setup() + the async-free onMounted (activateTheme /
  // setupConnectivityListeners / loadWaiterCalls / realtime.connect / setInterval /
  // visibilitychange) + the whole own-template (skip-link, brand + role badge,
  // connectivity chips, theme toggle, sign-out button, and the <main> landmark wrapping
  // <RouterView />) must render and NOT throw. Guest (session.user === null) →
  // isTenantOwner false → the owner-view link is absent.
  it("mounts the waiter chrome without a setup() crash", async () => {
    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);

    // Skip-link — the layout's own a11y landmark (same shared key every layout uses).
    // Uniquely the native <a href="#main-content"> (the RouterLink stub has no href).
    const skip = wrapper.find("a[href='#main-content']");
    expect(skip.exists()).toBe(true);
    expect(skip.text()).toBe("common.skipToMain");

    // Exactly ONE focusable <main id="main-content"> landmark (single-main pattern).
    const mains = wrapper.findAll("main");
    expect(mains).toHaveLength(1);
    expect(mains[0].attributes("id")).toBe("main-content");
    // tabindex="-1" makes the landmark programmatically focusable for the route-change
    // focus guard (WCAG 2.4.3), mirroring the other layouts.
    expect(mains[0].attributes("tabindex")).toBe("-1");
    // The routed page renders INSIDE the main landmark (RouterView stub).
    expect(mains[0].find("[data-test='page']").exists()).toBe(true);

    // Waiter-chrome own-template keys: the role badge + the sign-out button (both always
    // visible to every waiter/staff user) are the crash anchors.
    const text = wrapper.text();
    expect(text).toContain("waiterLayout.role");
    expect(text).toContain("common.signOut");
    // Guest / non-owner → the owner-view link (the session.isTenantOwner branch) is absent.
    expect(text).not.toContain("waiterLayout.ownerView");
  });

  // ── (2) owner viewing the waiter surface: the isTenantOwner branch renders ──
  // The template's ONLY session-conditional branch is v-if="session.isTenantOwner" (the
  // "back to owner dashboard" link): a tenant OWNER using the waiter surface sees it; a
  // plain tenant_staff waiter (isTenantOwner false) does not. Seeding role: "tenant_owner"
  // flips the getter true and renders that branch — while re-confirming setup() + the full
  // chrome render cleanly over a POPULATED session store.
  it("renders the owner-view link when the session is a tenant owner (isTenantOwner branch)", async () => {
    useSessionStore().$patch({
      user: { id: 1, role: "tenant_owner" },
      loaded: true,
    });

    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // The owner-view link now renders (isTenantOwner === true) — the RouterLink stub
    // renders its slot, so the key is present in the text.
    expect(text).toContain("waiterLayout.ownerView");
    // Core chrome still renders over the seeded store (no regression on the shared paths).
    expect(text).toContain("waiterLayout.role");
    expect(text).toContain("common.signOut");
  });
});
