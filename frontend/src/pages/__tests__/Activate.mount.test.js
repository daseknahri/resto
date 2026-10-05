/**
 * Mount smoke test for Activate.vue (the account/tenant activation page, ~238 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined
 * access, a bad Intl combo, a bad import) was never caught by a test".
 * shallowMount runs the page's REAL setup() + onMounted, so any such crash fails
 * CI here instead of in production.
 *
 * WHAT THIS PAGE IS (verified by reading it): a pure FORM page — token + new
 * password + confirm, then submit. It reads its activation identifier from
 * `route.query.token` (a QUERY param, NOT a route param) inside onMounted, which
 * only seeds the token <input>; there is NO mount-time fetch and NO async at
 * mount. The activation POST (/activate/, via the activation store) and the
 * resend POST (/resend-activation/, via lib/api) fire ONLY on user submit — never
 * at mount — so the api mock here is purely defensive. Because it is a form,
 * there is no "loading / valid-activation payload (tenant name, email)" state to
 * drive: the page's only distinct own-template branches are the default form and
 * the store-driven "token expired/used → resend" block. The two cases cover both.
 * (Per the brief: largely a form → one solid default case suffices; case (2) adds
 * the page's OTHER own-template branch for real extra coverage.)
 *
 * Stores/api at mount: useActivationStore + useSessionStore run for real under a
 * fresh pinia (neither fetches at mount); lib/api is mocked (only hit on submit).
 * vue-router: the page imports { useRoute, useRouter } and calls both at setup —
 * useRoute().query.token is read in onMounted — so vue-router is mocked with a
 * vi.hoisted mutable query holder (referenced inside the vi.mock factory → must be
 * hoisted, else "0 test" TDZ). This page's template imports no RouterLink and no
 * child components, so shallowMount needs no extra stubs. No timers / observers /
 * scrollIntoView at mount, so none are stubbed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// The page destructures ONLY { t } from useI18n. Echo the key so template
// assertions can anchor on stable own-template i18n keys.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// Defensive api mock: nothing is fetched at mount. /activate/ (activation store)
// and /resend-activation/ (this module) fire only on user submit. Stub both verbs
// so no real network call can ever escape a future edit.
vi.mock("../../lib/api", () => ({
  // shared canonical extractor (added to lib/api; mock returns the fallback)
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// The page imports { useRoute, useRouter } and calls both at setup. onMounted
// reads route.query.token, so a token is seeded here. Hoisted so the mutable
// holder can be referenced from inside the vi.mock factory without a TDZ error.
const { routeState, routerSpies } = vi.hoisted(() => ({
  routeState: { params: {}, query: { token: "seed-token-abc123" } },
  routerSpies: { push: null, replace: null },
}));
vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => routerSpies,
}));

import { useActivationStore } from "../../stores/activation";
import Activate from "../Activate.vue";

// The already-activated actions use the global <RouterLink> (not imported):
// a pass-through stub that exposes `to` so the targets can be asserted.
const RouterLinkStub = {
  props: ["to"],
  template: '<a :data-to="JSON.stringify(to)"><slot /></a>',
};
const mountPage = () => shallowMount(Activate, { global: { stubs: { RouterLink: RouterLinkStub } } });

describe("Activate — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // session store instantiates for real; clear any localStorage-backed state so
    // tests don't leak across each other.
    localStorage.clear();
    setActivePinia(createPinia());
    // Reset the route query to the default (token present) before each test.
    routeState.params = {};
    routeState.path = "/activate";
    routeState.query = { token: "seed-token-abc123" };
    vi.clearAllMocks();
    routerSpies.push = vi.fn();
    routerSpies.replace = vi.fn(() => Promise.resolve());
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) default mount: token present in the query ──────────────────────────
  // The core guard: setup() + onMounted (which reads route.query.token and seeds
  // the token field) + the whole form template must render without throwing.
  it("mounts the default activation form (token seeded from the query) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // onMounted read the activation identifier from route.query.token and seeded it.
    expect(wrapper.vm.token).toBe(routeState.query.token);
    // Own-template anchors always present in the default form branch:
    expect(wrapper.text()).toContain("activateAccount.title"); // header
    expect(wrapper.text()).toContain("activateAccount.activate"); // submit CTA
  });

  // ── (2) store-driven resend branch: token expired/used ─────────────────────
  // The page's OTHER own-template branch: pre-seeding the activation store to
  // tokenExpiredOrUsed:true renders the <div v-if="store.tokenExpiredOrUsed">
  // resend-email block (resendSent is false → the email input + resend button
  // render). This exercises a whole conditional chunk of the page's own template
  // the default mount never renders — and must not throw.
  it("mounts the token-expired/used resend branch without a crash", async () => {
    useActivationStore().$patch({ tokenExpiredOrUsed: true });

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Resend branch rendered its own-template keys:
    expect(wrapper.text()).toContain("activateAccount.resendPrompt");
    expect(wrapper.text()).toContain("activateAccount.resendAction");
    // The base form still renders alongside the resend block.
    expect(wrapper.text()).toContain("activateAccount.title");
  });

  // ── (3) token hygiene: the live token leaves the address bar ───────────────
  it("strips the token from the URL once it is in the form, keeping other params", async () => {
    routeState.query = { token: "seed-token-abc123", next: "/owner" };
    wrapper = mountPage();
    await flushPromises();

    expect(wrapper.vm.token).toBe("seed-token-abc123");
    expect(routerSpies.replace).toHaveBeenCalledTimes(1);
    const target = routerSpies.replace.mock.calls[0][0];
    expect(target.path).toBe("/activate");
    expect(target.query).toEqual({ next: "/owner" });
  });

  it("does not navigate when the URL has no token", async () => {
    routeState.query = {};
    wrapper = mountPage();
    await flushPromises();
    expect(routerSpies.replace).not.toHaveBeenCalled();
  });

  // ── (4) already-activated account: offer Sign in / Forgot password ─────────
  it("offers Sign in and Forgot password actions for an already-activated account", async () => {
    routeState.query = { next: "/owner" };
    useActivationStore().$patch({
      error: 'This account is already activated. Sign in, or use "Forgot password" to reset your password.',
      alreadyActivated: true,
    });
    wrapper = mountPage();
    await flushPromises();

    const links = wrapper.findAll("a");
    const targets = links.map((a) => JSON.parse(a.attributes("data-to")));
    expect(targets).toContainEqual({ name: "signin", query: { next: "/owner" } });
    expect(targets).toContainEqual({ name: "forgot-password" });
    expect(wrapper.text()).toContain("activateAccount.signInAction");
    expect(wrapper.text()).toContain("activateAccount.forgotPasswordAction");
    // Not the expired-token resend flow.
    expect(wrapper.text()).not.toContain("activateAccount.resendPrompt");
  });

  it("does not render the account actions for other errors", async () => {
    useActivationStore().$patch({ error: "Invalid token", alreadyActivated: false });
    wrapper = mountPage();
    await flushPromises();
    expect(wrapper.text()).not.toContain("activateAccount.signInAction");
  });
});
