/**
 * Mount smoke test for AdminLayout.vue — the platform-admin chrome layout (~199 lines)
 * that WRAPS all 9 platform-admin routes with a persistent top nav bar + sign-out.
 *
 * WHY A LAYOUT TEST MATTERS MORE THAN A PAGE TEST: a layout wraps EVERY admin route,
 * so a setup()-time error here (a TDZ ReferenceError, an undefined lookup, an
 * unguarded browser API) white-screens the ENTIRE admin section — every admin page
 * at once — not just one page. This mounts the layout's real setup() (useI18n /
 * useRouter / useSessionStore / PLATFORM_NAME + the navLinks table + the
 * `$route.name` active-link bindings the template forces to evaluate) so any such
 * crash fails CI here instead of shipping a blank admin console.
 *
 * WHAT THIS LAYOUT IS (verified by reading it): the SIMPLEST full layout — NO
 * onMounted, NO fetch at mount, NO Leaflet / observers / intervals / WebSocket. Its
 * <script setup> destructures useI18n() as EXACTLY { t }, imports ONLY { useRouter }
 * from vue-router (NOT useRoute), reads PLATFORM_NAME (a real constant, left REAL),
 * and holds one local `signingOut` ref. The template has NO session-conditional
 * branch: the session store is touched ONLY inside handleSignOut() (fired on the
 * sign-out button click), so the chrome renders IDENTICALLY for a guest or a
 * signed-in admin. The "authenticated admin" case below is therefore a second
 * crash-guard over a populated store, not a distinct render branch (documented so a
 * future reader doesn't mistake it for one).
 *
 * Pattern-faithful to layouts/__tests__/PlainLayout.test.js (RouterView stub +
 * exactly-one <main id="main-content"> landmark + skip-link) and to
 * pages/__tests__/SignIn.mount.test.js (echo-{ t } i18n, real pinia session,
 * vue-router mocked), with ONE layout-specific addition: the template reads
 * `$route.name` in the nav-link v-for bindings (data-active / aria-current), which
 * is evaluated in AdminLayout's OWN scope BEFORE reaching the RouterLink stub — so a
 * `global.mocks.$route` is REQUIRED or `$route.name` throws a TypeError at render.
 * No existing test needed one (this is the first tested component using the $route
 * global property). Mocking vue-router to export ONLY { useRouter } is safe: the
 * whole load graph (session store → lib/api → axios/runtimeHost/translate/retry)
 * imports nothing else from vue-router.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n: echo the key (params appended as JSON) so assertions target the
// EXACT keys the layout's OWN template renders. AdminLayout destructures EXACTLY { t }.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// vue-router: AdminLayout imports ONLY { useRouter } and calls router.push exclusively
// inside handleSignOut (on button click), never at mount. Exporting just useRouter is
// safe here — nothing else in the load graph imports from vue-router.
vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// lib/api is pulled in transitively by the session store; it is NEVER called at mount
// (signOut only fires on click). Mock it defensively so importing the store stays
// hermetic (no lingering real axios instance), mirroring SignIn.mount.test.js.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import AdminLayout from "../AdminLayout.vue";
import { useSessionStore } from "../../stores/session";

// <RouterView> and <RouterLink> are GLOBAL (un-imported) components normally registered
// by the router plugin; the plugin-less test app resolves them via these stubs (a no-op
// <a> pass-through for RouterLink, a page marker for RouterView). Neither is referenced
// inside a vi.mock factory, so neither needs vi.hoisted.
//
// $route: the nav v-for reads `$route.name` (data-active / aria-current) in AdminLayout's
// own render scope, so it MUST be provided or `$route.name` throws. name:"admin-console"
// also drives the active-link branch for the first nav link.
const mountLayout = () =>
  mount(AdminLayout, {
    global: {
      mocks: {
        $route: { name: "admin-console" },
      },
      stubs: {
        RouterView: { template: "<div data-test='page'>page</div>" },
        RouterLink: { props: ["to"], template: "<a><slot /></a>" },
      },
    },
  });

describe("AdminLayout — mount smoke (admin chrome crash guard)", () => {
  let wrapper;

  beforeEach(() => {
    // Session/other stores can be localStorage-backed elsewhere; clear FIRST so no cache
    // leaks across tests (proven-recipe hygiene).
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) default mount: the whole admin chrome renders ─────────────────────
  // The core guard: the entire setup() and the whole own-template (skip-link, brand
  // title, the 9-item nav v-for with its $route.name active bindings, sign-out button,
  // and the <main> landmark wrapping <RouterView />) must render and not throw.
  it("mounts the admin chrome without a setup() crash", async () => {
    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);

    // Skip-link — the layout's own a11y landmark (same shared key PlainLayout uses).
    const skip = wrapper.find("a[href='#main-content']");
    expect(skip.exists()).toBe(true);
    expect(skip.text()).toBe("common.skipToMain");

    // Exactly ONE focusable <main id="main-content"> landmark (single-main pattern).
    const mains = wrapper.findAll("main");
    expect(mains).toHaveLength(1);
    expect(mains[0].attributes("id")).toBe("main-content");
    // tabindex="-1" makes the landmark programmatically focusable for the route-change
    // focus guard (WCAG 2.4.3), mirroring PlainLayout.
    expect(mains[0].attributes("tabindex")).toBe("-1");
    // The routed page renders INSIDE the main landmark (RouterView stub).
    expect(mains[0].find("[data-test='page']").exists()).toBe(true);

    // Chrome own-template keys: brand title (params echoed), a nav link, and sign-out.
    const text = wrapper.text();
    expect(text).toContain("adminLayout.title");
    expect(text).toContain("adminLayout.console");
    expect(text).toContain("common.signOut");
  });

  // ── (2) authenticated platform-admin: chrome still renders over a seeded store ──
  // AdminLayout has NO session-conditional branch (session is used only inside the
  // click-time handleSignOut), so this does not exercise a distinct branch — it is a
  // second crash-guard confirming setup() and the full chrome render cleanly over a
  // POPULATED session store (isPlatformAdmin/isTenantOwner getters now truthy/typed).
  it("mounts the chrome over a seeded platform-admin session without a crash", async () => {
    useSessionStore().$patch({
      user: { id: 1, role: "platform_admin", is_platform_admin: true },
      loaded: true,
    });

    expect(() => {
      wrapper = mountLayout();
    }).not.toThrow();

    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    // Same chrome renders (no session branch) — the nav + sign-out are the crash anchors.
    const text = wrapper.text();
    expect(text).toContain("adminLayout.console");
    expect(text).toContain("common.signOut");
  });
});
