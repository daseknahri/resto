/**
 * Mount smoke test for Unauthorized.vue (the 403 / access-denied page, ~139 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined access,
 * bad import) was never caught by a test". Mounting the page runs its real setup() —
 * useRoute()/useRouter()/useSessionStore()/useI18n() plus the whole computed graph
 * (reason, next, message, signInLink, showSignIn, showAdmin, showOnboarding) that the
 * template forces to evaluate — so any such crash fails CI here instead of in prod.
 *
 * WHAT THIS PAGE IS (verified by reading it): a static 403 landing page. It has NO
 * onMounted, NO fetch, NO lib/api import — pure computed off route.query + session
 * getters. It imports { useRoute, useRouter } from vue-router (route.query.reason /
 * route.query.next drive the message + which action links show; router is used only by
 * the switchAccount click handler, never at mount). <RouterLink> appears in the
 * template but is a GLOBAL component (NOT imported — confirmed by grep) → provided as a
 * pass-through global.stubs.RouterLink; because that stub is never referenced inside a
 * vi.mock factory, no vi.hoisted is needed here.
 *
 * Pattern-faithful to pages/__tests__/WaiterJoin.mount.test.js +
 * SuperAppHub.mount.test.js, minus the api mock (this page makes no API call):
 *   - shallowMount runs the page's own setup() (the thing under test)
 *   - real pinia (the session store runs for real; isAuthenticated = !!user)
 *   - useI18n mocked to echo keys deterministically ({ t } only — the page
 *     destructures just t)
 *   - vue-router mocked (the page imports { useRoute, useRouter })
 *
 * The page branches on session: the switch-account <button> (the ONLY <button> in the
 * template) is gated by session.isAuthenticated, so wrapper.find("button") cleanly
 * separates the guest branch (case 1) from the authenticated branch (case 2).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// The page imports { useRoute, useRouter } from vue-router. useRoute supplies the
// query (reason/next drive the computeds); useRouter is only touched by the
// switchAccount click handler, never at mount. Empty query = the generic 403 state.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { useSessionStore } from "../../stores/session";
import Unauthorized from "../Unauthorized.vue";

// <RouterLink> is a global (un-imported) component here → pass-through stub so the
// action links render their slot text instead of an unresolved-component warning.
const mountPage = () =>
  shallowMount(Unauthorized, {
    global: {
      stubs: {
        RouterLink: { props: ["to"], template: "<a><slot /></a>" },
      },
    },
  });

describe("Unauthorized — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) guest / generic 403 ───────────────────────────────────────────────
  // The core guard: setup() + the whole computed graph + the card template must
  // render for an unauthenticated visitor and not throw. showSignIn is true (no
  // user) so the sign-in link shows; session.isAuthenticated is false so the
  // switch-account <button> — the only <button> in the template — is absent.
  it("mounts for a guest (generic 403) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Own-template heading — the <h1>, always present regardless of reason/role.
    expect(wrapper.text()).toContain("unauthorized.title");
    // Guest: not authenticated → the switch-account button is NOT rendered.
    expect(wrapper.find("button").exists()).toBe(false);
  });

  // ── (2) authenticated visitor (session branch) ────────────────────────────
  // Seeds session.user so isAuthenticated flips true — the page's session branch.
  // Now the switch-account <button> (v-if="session.isAuthenticated") renders, and
  // setup() must still not throw. This exercises the isAuthenticated / showSignIn
  // getters against a real user object.
  it("mounts for an authenticated user and renders the switch-account action", async () => {
    useSessionStore().$patch({ user: { id: 1, name: "Test User" }, loaded: true });

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Heading still present in the authenticated branch.
    expect(wrapper.text()).toContain("unauthorized.title");
    // Authenticated: the switch-account button now renders (the session branch).
    expect(wrapper.find("button").exists()).toBe(true);
  });
});
