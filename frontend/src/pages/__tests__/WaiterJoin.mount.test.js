/**
 * Mount smoke test for WaiterJoin.vue (the staff self-join flow, ~437 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined map
 * access, bad import) was never caught by a test". Mounting the page runs its
 * real setup() — an onMounted that awaits tenant.fetchMeta(), the useInstallPrompt
 * PWA branch, a tenantName computed, and the whole multi-branch card template — so
 * a crash in any of it fails CI here instead of in production.
 *
 * WHAT THIS PAGE IS (verified by reading it): despite the "join" name, there is NO
 * invite token / code / PIN. The page does NOT call useRoute(), has no defineProps,
 * and reads no route param/query. It imports ONLY { useRouter } from vue-router (for
 * router.replace after a successful sign-in). The "join" flow is: install the PWA,
 * then sign in with email + password via session.signIn (MFA + forced-password-change
 * are secondary form branches). The page's only "loaded state" axis is tenant.meta —
 * the restaurant branding name shown in the <h1>. So the two cases below are the
 * empty-branding (fetch → {}) path and the loaded-branding (meta pre-seeded) path.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * pages/__tests__/SuperAppHub.mount.test.js (URL-routed api mock):
 *   - shallowMount runs the page's own setup() (the thing under test)
 *   - real pinia (session + tenant stores run for real) + a mocked lib/api
 *   - useI18n mocked to return deterministic keys ({ t } only — the page destructures
 *     just t)
 *   - vue-router mocked (the page imports { useRouter }; useRoute is added defensively
 *     even though the page never calls it)
 *   - useInstallPrompt mocked: it is jsdom-safe unmocked (window.matchMedia?.(...) is
 *     optional-chained) but carries module-level singleton state + addEventListener;
 *     mocking pins isStandalone/canInstall so the install-steps + sign-in-form branch
 *     renders deterministically regardless of the global test setup.
 *
 * tenant.fetchMeta() uses the REAL staleCache (localStorage-backed), so localStorage
 * is cleared in beforeEach — otherwise case (1)'s empty {} meta write is served from
 * cache to later tests within the 5-min TTL.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// URL-routed api mock: onMounted fires GET /meta/ via the tenant store. Default:
// everything resolves empty so the fresh-staff path renders. post() is only used by
// submitForcePasswordChange (never at mount) but is stubbed for completeness.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// The page imports ONLY { useRouter } from vue-router (router.replace on success).
// It does NOT import RouterLink and does NOT call useRoute — useRoute is mocked
// defensively (harmless) to match the proven template shape.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

// useInstallPrompt drives the PWA install branch. Fix isStandalone=false so the
// install steps + sign-in form render (the default staff-facing state).
vi.mock("../../composables/useInstallPrompt", () => ({
  useInstallPrompt: () => ({
    canInstall: false,
    isStandalone: false,
    install: vi.fn(),
  }),
}));

import { useTenantStore } from "../../stores/tenant";
import WaiterJoin from "../WaiterJoin.vue";

const mountPage = () => shallowMount(WaiterJoin);

describe("WaiterJoin — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // tenant.fetchMeta() uses the REAL localStorage-backed staleCache — clear it so
    // case (1)'s empty {} meta write isn't served (still "fresh") to a later test.
    localStorage.clear();
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
    _routes = {};
  });

  // ── (1) fresh staff: no tenant meta yet ───────────────────────────────────
  // The core guard: setup() + the async onMounted (fetchMeta → { data: {} }) + the
  // whole card template must render with empty branding and not throw. tenantName
  // falls back to t('waiterJoin.kicker'); the sign-in form is the default branch
  // (!mfaRequired && !forcePasswordChangeRequired).
  it("mounts a fresh staff member (no tenant meta) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Own-template anchors, always present in the default sign-in branch:
    expect(wrapper.text()).toContain("signIn.identifier"); // identifier field label
    expect(wrapper.text()).toContain("waiterJoin.signInCta"); // page-own submit CTA
    expect(wrapper.text()).toContain("waiterJoin.installTitle"); // non-standalone install step
  });

  // ── (2) loaded branding: tenant meta present ──────────────────────────────
  // Drives the loaded path: with tenant.meta pre-seeded, onMounted short-circuits
  // (no fetch) and the <h1> renders the real restaurant name via the tenantName
  // computed — the page's only "loaded state" difference. The sign-in form must
  // still render (largely a form page: one solid loaded case beyond the default).
  it("mounts with loaded tenant branding (restaurant name in the header)", async () => {
    useTenantStore().$patch({ meta: { name: "Chez Test" } });

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Loaded assertion: tenantName computed rendered the restaurant name.
    expect(wrapper.text()).toContain("Chez Test");
    // Sign-in form still present alongside the branding.
    expect(wrapper.text()).toContain("waiterJoin.signInCta");
  });
});
