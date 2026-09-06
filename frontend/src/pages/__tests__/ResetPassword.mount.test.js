/**
 * Mount smoke test for ResetPassword.vue (the set-a-new-password form, ~177 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined
 * access, bad import) was never caught by a test". Mounting the page runs its
 * real setup() — the useRoute()/useI18n() wiring, the `signinLink` computed that
 * reads route.query.next, the onMounted() that reads the reset token out of
 * route.query.token, and the whole form template — so a crash in any of it fails
 * CI here instead of in production.
 *
 * WHAT THIS PAGE IS (verified by reading it): a single reset form. It imports
 * ONLY { useRoute } from vue-router (no useRouter, no RouterLink import — the
 * <RouterLink> in the template is the global component, so it is stubbed via
 * global.stubs, not through the vue-router factory). onMounted seeds `token`
 * from `route.query.token` when present. The reset POST
 * (api.post('/password-reset/confirm/', ...)) fires only on submit — there is NO
 * mount-time fetch. submit() runs client-side validation first (token required,
 * password >= 8, passwords match) and early-returns without touching the API when
 * validation fails.
 *
 * Pattern-faithful to pages/__tests__/MarketplaceMenuPage.mount.test.js +
 * pages/__tests__/WaiterJoin.mount.test.js:
 *   - shallowMount runs the page's own setup() (the thing under test)
 *   - real pinia (createPinia per test) — the page uses no store, but this keeps
 *     the harness identical to the proven templates
 *   - lib/api mocked defensively (default { get, post }); post is asserted, never
 *     expected at mount
 *   - useI18n mocked to echo the key ({ t } only — the page destructures just t)
 *   - vue-router mocked: useRoute returns a vi.hoisted mutable holder so a test
 *     can seed (or omit) route.query.token before mount; useRouter provided
 *     defensively even though the page never calls it
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// Defensive api mock. The reset POST fires only on submit; there is no mount-time
// fetch. get() is stubbed for completeness only.
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// vi.hoisted mutable route holder: hoisted above the imports so it can be
// referenced inside the vue-router factory below, and mutated per-test to seed
// (or omit) route.query.token before mount. onMounted reads route.query.token;
// the signinLink computed reads route.query.next.
const routeState = vi.hoisted(() => ({ params: {}, query: {} }));

// The page imports ONLY { useRoute } from vue-router. useRouter is provided
// defensively (never called by this page). RouterLink is NOT imported here — it
// is the global component and is stubbed via global.stubs in mountPage().
vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import api from "../../lib/api";
import ResetPassword from "../ResetPassword.vue";

const mountPage = () =>
  shallowMount(ResetPassword, {
    global: {
      stubs: {
        // global-component <RouterLink> (not imported) → pass-through stub so the
        // sign-in link slot renders and Vue doesn't warn on an unresolved component.
        RouterLink: { template: "<a><slot /></a>" },
      },
    },
  });

describe("ResetPassword — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // No cached-store / staleCache dependency here, but clear localStorage first
    // to match the proven template hygiene and stay isolated from other suites.
    localStorage.clear();
    setActivePinia(createPinia());
    routeState.params = {};
    routeState.query = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) default mount: token seeded from ?token= in the URL ─────────────────
  // The core guard: setup() + the onMounted token-read + the whole form template
  // must render without throwing, and onMounted must copy the URL token into the
  // form field.
  it("mounts with a token seeded from the URL query without a setup() crash", async () => {
    routeState.query = { token: "reset-token-abc123" };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Own-template heading (i18n mock echoes the key → asserts the exact key+namespace).
    expect(wrapper.text()).toContain("resetPassword.title");
    // onMounted read the token out of route.query.token into the form.
    expect(wrapper.vm.token).toBe("reset-token-abc123");
    // No POST at mount — the reset only fires on submit.
    expect(api.post).not.toHaveBeenCalled();
  });

  // ── (2) missing-token branch + client-side validation submit ────────────────
  // Mount with no ?token= in the URL: onMounted's `if` guard is false, so token
  // stays "". Submitting then hits submit()'s required-token guard, which renders
  // an own-template field error and early-returns WITHOUT calling the API. This
  // exercises the missing-token branch, the submit() validation path, and proves
  // the API boundary is not touched on an invalid submit.
  it("mounts with no token and surfaces the required-token error on submit (no API call)", async () => {
    // routeState.query is already {} from beforeEach.
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Missing-token branch of onMounted: field left empty.
    expect(wrapper.vm.token).toBe("");

    await wrapper.vm.submit();
    await flushPromises();

    // submit() early-returned on the required-token guard — no network call.
    expect(api.post).not.toHaveBeenCalled();
    // Own-template validation error rendered (key echoed by the i18n mock).
    expect(wrapper.text()).toContain("resetPassword.tokenRequired");
  });
});
