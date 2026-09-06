/**
 * Mount smoke test for OwnerLayout.vue — the OWNER chrome wrapper (~1015 lines) that
 * WRAPS every owner route (dashboard, orders, menu-builder, tables, reservations,
 * analytics, wallet, staff, profile…). It is the most composable-heavy layout in the
 * app: it wires SEVEN composables (vocabulary, owner-theme, PWA install, web-push,
 * owner-realtime WebSocket, waiter-calls, staff-chat), three pinia stores, an async
 * onMounted (theme paint + chunk prefetch + WS connect + tenant.fetchMeta +
 * order.fetchOrders + a 30s background poll + document listeners) and a route-change
 * watch.
 *
 * WHY A LAYOUT TEST MATTERS MORE THAN A PAGE TEST: a layout wraps EVERY owner route, so
 * a setup()-time error here (a TDZ ReferenceError, an undefined lookup, an unguarded
 * browser API) white-screens the ENTIRE owner section — every owner page at once — not
 * just one page. Mounting the layout runs its real setup() + onMounted so any such crash
 * fails CI here instead of shipping a blank owner console.
 *
 * Pattern-faithful to layouts/__tests__/{AdminLayout,LandingLayout}.mount.test.js (the
 * $route global-mock, ref-returning composable mocks via `const { ref } = await
 * import("vue")` in async factories, RouterView/RouterLink stubs, real-pinia stores) and
 * pages/__tests__/OwnerHome.mount.test.js (URL-routed api mock + async onMounted).
 *
 * MOCKING STANCE — why EVERY WS/push/realtime/theme/vocab composable is mocked:
 *   - useOwnerRealtime → the layout does useOwnerRealtime(cb) then onMounted(connect) /
 *     onBeforeUnmount(disconnect). The real connect() calls `new WebSocket(url)` and, on
 *     failure, schedules a `setTimeout` reconnect that fires AFTER teardown → an
 *     unhandled error that fails the CI job even with every assertion passing (the same
 *     class as the Leaflet-at-mount leak). Mocking the WRAPPER neutralizes it.
 *   - usePushNotifications / useInstallPrompt / useOwnerTheme touch serviceWorker /
 *     Notification / beforeinstallprompt / document at module scope — mocking replaces
 *     those module bodies entirely, so none of them run.
 *   - useWaiterCalls / useStaffChat are module-level singletons that hit the network on
 *     load(); mocking keeps the mount hermetic (their api is never called).
 *
 * LAYOUT-SPECIFIC $route TRAP (confirmed on AdminLayout + LandingLayout this campaign):
 * the nav RouterLinks bind :data-active / :aria-current from `$route.path` DIRECTLY (e.g.
 * `$route.path === '/owner'`, `$route.path.startsWith('/owner/orders')`). Those
 * expressions are evaluated in OwnerLayout's OWN render scope BEFORE the RouterLink stub,
 * and shallowMount injects no $route — so a `global.mocks.$route` is REQUIRED or
 * `$route.path` throws a TypeError at render. The script's useRouter() return
 * (router.currentRoute.value.{path,fullPath}) is separately mocked.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// ── i18n: echo the key (params appended as JSON) so assertions target the EXACT keys the
// layout's OWN template renders. OwnerLayout destructures EXACTLY { t }.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// ── URL-routed api mock (proven OwnerHome pattern). At mount the real stores fire
// GET /meta/ (tenant.fetchMeta, case 1 only — case 2 seeds meta so it is skipped) and
// GET /owner/orders/ (order.fetchOrders, both cases). Default { data: {} } → the empty /
// fresh-owner path. Tests set _routes to drive the populated path.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => String(url).includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// ── vue-router: OwnerLayout imports ONLY { useRouter }. router.currentRoute.value.{path,
// fullPath} are read in activeWorkspaceLabel, the route-change watch, and the poll helpers;
// router.push fires only inside the click-time signOut. RouterView/RouterLink are GLOBAL
// components (not imported) → provided via global.stubs, NOT here. useRoute is exported
// defensively (nothing in the load graph imports it, but it costs nothing).
vi.mock("vue-router", () => ({
  useRouter: () => ({
    push: vi.fn(),
    currentRoute: { value: { path: "/owner", fullPath: "/owner", query: {}, params: {}, name: "owner-home" } },
  }),
  useRoute: () => ({ path: "/owner", fullPath: "/owner", query: {}, params: {}, name: "owner-home" }),
}));

// ── useVocabulary → the layout destructures { catalog: vocabCatalog } and reads
// vocabCatalog.value (in menuBuilderLabel + activeWorkspaceLabel), so `catalog` MUST be a
// REAL ref, not a plain value. (Real shape also has isShop/itemSingular/itemPlural/
// groupSingular/groupPlural — none destructured here.)
vi.mock("../../composables/useVocabulary", async () => {
  const { ref } = await import("vue");
  return { useVocabulary: () => ({ catalog: ref("Menu") }) };
});

// ── useOwnerTheme → { theme: ownerTheme, toggleTheme, activate, deactivate }. onMounted
// calls activate() (paint), onBeforeUnmount calls deactivate() (strip attr); the template
// reads ownerTheme === 'dark' (auto-unwrapped) for the toggle icon. Mocking also avoids
// the real module-singleton localStorage/document.documentElement writes leaking across
// tests.
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

// ── useOwnerRealtime(onEvent) → mock the WRAPPER so connect() opens NO real WebSocket and
// schedules NO reconnect setTimeout (the post-teardown-leak trap). connect fires in
// onMounted, disconnect in onBeforeUnmount.
vi.mock("../../composables/useOwnerRealtime", () => ({
  useOwnerRealtime: () => ({ connect: vi.fn(), disconnect: vi.fn() }),
}));

// ── useWaiterCalls → { pending: ref([]), load, acknowledge, handleRealtime }. The template
// reads waiterCallsPending.length (auto-unwrapped) and v-fors over it; load() fires in
// onMounted (gated on showWaiter). acknowledge/handleRealtime return promises in the real
// composable (the layout .then()s handleRealtime), so mock them promise-returning.
vi.mock("../../composables/useWaiterCalls", async () => {
  const { ref } = await import("vue");
  return {
    useWaiterCalls: () => ({
      pending: ref([]),
      load: vi.fn(),
      acknowledge: vi.fn(() => Promise.resolve()),
      handleRealtime: vi.fn(() => Promise.resolve(false)),
    }),
  };
});

// ── useStaffChat → the layout destructures only { handleRealtime: handleChatRealtime };
// the full real shape is mocked for fidelity (note: the real `error` is ref(false), not
// ref(null)). The <OwnerStaffChat> child that consumes the rest is shallowMount-stubbed.
vi.mock("../../composables/useStaffChat", async () => {
  const { ref } = await import("vue");
  return {
    useStaffChat: () => ({
      messages: ref([]),
      unread: ref(0),
      isOpen: ref(false),
      loading: ref(false),
      error: ref(false),
      load: vi.fn(),
      send: vi.fn(),
      handleRealtime: vi.fn(),
      open: vi.fn(),
      close: vi.fn(),
    }),
  };
});

// ── useInstallPrompt → { canInstall, install: pwaInstall }. canInstall ref(false) → the
// install button stays hidden and never fires a real beforeinstallprompt.
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

// ── usePushNotifications → the layout destructures { supported, enabled, subscribed,
// loading, subscribe, unsubscribe, autoRestore, checkEnabled }. NOTE: in the real
// composable `supported` is a PLAIN boolean (not a ref) — mocked as a plain boolean to
// match. onMounted does `checkEnabled().then(() => { if (enabled.value) autoRestore() })`,
// so checkEnabled MUST return a promise and enabled MUST be a ref (its .value is read).
// supported:false keeps the push bell hidden (`v-if="pushSupported && pushEnabled"`).
vi.mock("../../composables/usePushNotifications", async () => {
  const { ref } = await import("vue");
  return {
    usePushNotifications: () => ({
      supported: false,
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

import OwnerLayout from "../OwnerLayout.vue";
import { useSessionStore } from "../../stores/session";
import { useTenantStore } from "../../stores/tenant";

// <RouterView> / <RouterLink> are GLOBAL (un-imported) components normally registered by
// the router plugin; the plugin-less test app resolves them via these stubs. RouterView's
// stub swallows its scoped slot, so the inner Transition/KeepAlive/<component :is> never
// render (chrome-only smoke test). Transition is stubbed to render its child synchronously
// so the grace-period banner (a real <Transition>) is deterministic in the seeded case.
// $route is read directly in the nav RouterLink bindings (see header) → global.mocks.
const mountLayout = () =>
  shallowMount(OwnerLayout, {
    global: {
      mocks: {
        $route: { name: "owner-home", path: "/owner", query: {}, params: {} },
        $router: { push: vi.fn() },
      },
      stubs: {
        RouterView: { template: "<div data-test='page'></div>" },
        RouterLink: { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
      },
    },
  });

describe("OwnerLayout — mount smoke (owner chrome crash guard)", () => {
  let wrapper;

  beforeEach(() => {
    // Clear FIRST: owner-theme, the tenant staleCache('meta'), and the push LS key are all
    // localStorage-backed; without this, test 1's empty-meta cache write could be served to
    // test 2 (proven-recipe hygiene, even though useOwnerTheme is mocked here).
    localStorage.clear();
    setActivePinia(createPinia());
    // requestIdleCallback is jsdom-missing → the layout's prefetchOwnerChunks() would fall
    // back to setTimeout(run, 1500), which fires real dynamic page imports AFTER teardown
    // (a fire-and-forget leak). Stub it as a no-op that never invokes the callback so those
    // prefetch imports never run. (It is the ONLY jsdom-missing API the layout touches at
    // mount — AudioContext / Notification are guarded and fire only on later alerts.)
    window.requestIdleCallback = vi.fn();
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Unmount runs onBeforeUnmount → disconnects (mocked) realtime, clears the 30s order
    // poll interval, and removes the pointerdown/visibilitychange document listeners — so no
    // socket / timer / listener leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
    delete window.requestIdleCallback;
  });

  // ── (1) default mount: the whole owner chrome renders ─────────────────────
  // The core guard: the async onMounted (activateTheme + prefetch + WS connect +
  // fetchMeta + fetchOrders + poll setup + listeners) and the whole own-template
  // (skip-link, brand title, the desktop + mobile nav with their $route.path active
  // bindings, the settings trigger, and the <main> landmark wrapping <RouterView />)
  // must render with empty data and not throw.
  it("mounts the owner chrome without a setup() crash", async () => {
    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();

    await flushPromises();
    await flushPromises(); // drain fetchMeta + fetchOrders + the un-awaited checkEnabled().then()

    expect(wrapper.exists()).toBe(true);

    // Skip-link — the layout's own a11y landmark (shared key).
    const skip = wrapper.find("a[href='#main-content']");
    expect(skip.exists()).toBe(true);
    expect(skip.text()).toBe("common.skipToMain");

    // Exactly ONE focusable <main id="main-content"> landmark, with the routed page inside.
    const mains = wrapper.findAll("main");
    expect(mains).toHaveLength(1);
    expect(mains[0].attributes("id")).toBe("main-content");
    // tabindex="-1" makes the landmark programmatically focusable for the route-change
    // focus guard (WCAG 2.4.3).
    expect(mains[0].attributes("tabindex")).toBe("-1");
    // The routed page renders INSIDE the main landmark (RouterView stub).
    expect(mains[0].find("[data-test='page']").exists()).toBe(true);

    // Own-template chrome keys: a nav item + the fresh-owner fallback tenant name (empty
    // meta → tenant.meta.name undefined → the fallback key).
    const text = wrapper.text();
    expect(text).toContain("ownerLayout.dashboard");
    expect(text).toContain("ownerLayout.fallbackTenantName");
  });

  // ── (2) seeded owner: authenticated session + populated tenant meta ───────
  // The template has NO session-conditional branch (the session store is touched only inside
  // the click-time signOut), so seeding the session store is a SECOND CRASH-GUARD over a
  // populated store, NOT a distinct render branch. The MEANINGFUL render branches here are
  // TENANT-driven: a populated tenant.meta renders the real name (not the fallback key) and,
  // with payment_overdue_since set, the grace-period banner; a pending order lights the live
  // orders badge + sr-only live region. Seeding meta (truthy) also makes onMounted skip
  // fetchMeta, so the seeded meta survives.
  it("mounts over a seeded owner session + populated tenant meta (grace banner + orders badge)", async () => {
    useSessionStore().$patch({
      user: { id: 1, role: "tenant_owner", is_platform_admin: false, can_edit_tenant_menu: true },
      loaded: true,
    });
    useTenantStore().$patch({
      // name → real tenant name; payment_overdue_since = now → within the 7-day grace window.
      meta: { name: "Chez Testville", payment_overdue_since: new Date().toISOString() },
    });
    // Drive the active-orders poll so pendingOrdersCount > 0 (badge + sr-only live region).
    _routes = { "/owner/orders/": { data: { results: [{ id: 1, order_number: "A1", status: "pending" }] } } };

    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();

    await flushPromises();
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    const text = wrapper.text();
    // Populated meta → the real tenant name renders (the fresh-owner fallback key is absent).
    expect(text).toContain("Chez Testville");
    expect(text).not.toContain("ownerLayout.fallbackTenantName");
    // Within the grace window (graceExpired false, graceDaysRemaining = 7 > 1) → the
    // gracePeriodWarning branch of the overdue-payment banner renders.
    expect(text).toContain("ownerLayout.gracePeriodWarning");
    // One pending order → pendingOrdersCount > 0 → the sr-only orders live region renders.
    expect(text).toContain("ownerLayout.ordersBadgeLabel");
  });
});
