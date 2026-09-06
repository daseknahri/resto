/**
 * Mount smoke test for NotFound.vue (the 404 page, ~168 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined map
 * access, bad import) was never caught by a test". Mounting the page runs its real
 * setup() — so any such crash fails CI here instead of in production.
 *
 * WHAT THIS PAGE IS (verified by reading it): a small, fully SYNCHRONOUS 404 page.
 * There is NO onMounted, NO fetch, and NO lib/api import — so no api mock is needed.
 * setup() is just three computeds:
 *   - isOwnerHost  = session.canEditTenantMenu || session.isAuthenticated
 *   - isCustomerHost = !isOwnerHost
 *   - currentPath  = route.fullPath   (read by the aria-hidden path indicator)
 * The template's role-aware "go home" CTA branches on those:
 *   isOwnerHost → RouterLink to /owner ("notFound.goDashboard")
 *   else isCustomerHost → RouterLink to /browse ("notFound.goMenu")
 *   (the v-else "goHome" branch is unreachable — isCustomerHost is exactly
 *    !isOwnerHost — so only the two role branches ever render.)
 * That role flip is the page's only "loaded state" axis, giving two real cases:
 * a guest (customer branch) and an authenticated/owner user (dashboard branch).
 *
 * Pattern-faithful to pages/__tests__/SuperAppHub.mount.test.js +
 * pages/__tests__/OwnerHome.mount.test.js:
 *   - shallowMount runs the page's own setup() (the thing under test)
 *   - real pinia (setActivePinia(createPinia())) so the session store runs for real
 *   - useI18n mocked to echo keys ({ t } only — the page destructures just t)
 *   - vue-router mocked: the page imports { RouterLink, useRouter, useRoute }, so
 *     RouterLink is a vi.hoisted stub (a plain const in the hoisted vi.mock factory
 *     would hit the TDZ → "0 test" collection error) and useRoute returns fullPath
 *     (read by the currentPath computed).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// NotFound imports { RouterLink, useRouter, useRoute } from 'vue-router'.
// vi.hoisted: the vi.mock('vue-router') factory below is hoisted above the imports
// and runs during import evaluation — before a plain `const` in the file body would
// initialize — so referencing a plain const there hits the TDZ ("0 test" collection
// error). vi.hoisted makes the stub available to the hoisted factory.
// useRoute must expose fullPath: the currentPath computed reads route.fullPath.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({
  RouterLink: RouterLinkStub,
  useRoute: () => ({ fullPath: "/does-not-exist", params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

import { useSessionStore } from "../../stores/session";
import NotFound from "../NotFound.vue";

const mountPage = () =>
  shallowMount(NotFound, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  });

describe("NotFound — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // The page itself does not touch localStorage, but clearing first keeps the
    // suite hermetic and matches the proven mount-test template.
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) guest / default render → customer branch ──────────────────────────
  // The core guard: setup() (the three computeds) + the whole template must render
  // for a signed-out visitor and not throw. With user=null, isOwnerHost is false →
  // isCustomerHost true → the "View menu" (goMenu) CTA renders.
  it("mounts for a guest without a setup() crash and shows the 404 title + customer CTA", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Stable own-template heading (the <h1>) — the crash-guard anchor.
    expect(wrapper.text()).toContain("notFound.title");
    // Guest → customer branch renders the "View menu" CTA, not the dashboard CTA.
    expect(wrapper.text()).toContain("notFound.goMenu");
    expect(wrapper.text()).not.toContain("notFound.goDashboard");
    // The "go back" button is always present.
    expect(wrapper.text()).toContain("notFound.goBack");
  });

  // ── (2) authenticated owner → dashboard branch ────────────────────────────
  // Seeding session.user flips isAuthenticated (and canEditTenantMenu) true, so
  // isOwnerHost is true → the "Go to dashboard" (goDashboard) CTA renders instead.
  // Exercises the other side of the role computed the guest case can't reach.
  it("mounts for an authenticated owner and shows the dashboard CTA", async () => {
    useSessionStore().$patch({
      user: { id: 1, role: "tenant_owner", can_edit_tenant_menu: true },
      loaded: true,
    });

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("notFound.title");
    // Owner → dashboard branch renders the "Go to dashboard" CTA, not the menu CTA.
    expect(wrapper.text()).toContain("notFound.goDashboard");
    expect(wrapper.text()).not.toContain("notFound.goMenu");
  });
});
