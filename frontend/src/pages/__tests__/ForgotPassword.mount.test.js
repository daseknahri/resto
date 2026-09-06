/**
 * Mount smoke test for ForgotPassword.vue (the "request a password-reset link"
 * form, ~122 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined
 * access, bad import) was never caught by a test". Mounting the page runs its
 * real setup() — the useRoute()/useI18n() calls, the refs, the `signinLink`
 * computed (which reads route.query.next and is forced to evaluate by the
 * RouterLink :to binding), and the full form template — so a crash in any of it
 * fails CI here instead of in production.
 *
 * WHAT THIS PAGE IS (verified by reading it fully):
 *   - <script setup> imports: { computed, ref } from vue, { useRoute } from
 *     vue-router, useI18n, and the default api from ../lib/api.
 *   - useI18n is destructured as { t } ONLY.
 *   - There is NO onMounted and NO mount-time fetch. api is touched only inside
 *     submit() (api.post("/password-reset/request/", ...)) — never at mount.
 *   - useRoute() IS called: `signinLink` computed reads route.query.next. The
 *     template binds :to="signinLink" on <RouterLink>, so the computed evaluates
 *     during render — vue-router MUST be mocked so route.query exists.
 *   - <RouterLink> is used in the template but NOT imported from vue-router (it
 *     resolves via the app's global registration). In the plugin-less test app a
 *     RouterLink stub in global.stubs makes it a no-op <a> that still renders its
 *     slot and receives :to (mirrors pages/__tests__/AdminConsole.mount.test.js).
 *     The stub is a plain const — NOT referenced inside a vi.mock factory — so it
 *     needs no vi.hoisted (the TDZ trap only bites stubs used in a hoisted factory).
 *
 * Pattern-faithful to pages/__tests__/WaiterJoin.mount.test.js (useRoute-mocked
 * auth form, URL-routed lib/api mock, { t }-only useI18n) + AdminConsole
 * (global.stubs.RouterLink). Real pinia is set up defensively for pattern parity
 * even though this page uses no store; localStorage.clear() likewise (the page
 * has no staleCache), both harmless.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// URL-routed api mock. Nothing fetches at mount; api.post is used only by submit()
// (case 2). Default post resolves empty; per-test overrides use mockResolvedValueOnce.
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

// The page imports { useRoute } (signinLink reads route.query.next). useRouter is
// added defensively (harmless) even though this page never calls it.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import api from "../../lib/api";
import ForgotPassword from "../ForgotPassword.vue";

// <RouterLink> is global (not imported) — stub it to a no-op <a> that renders its
// slot and accepts :to (which forces the signinLink computed to evaluate). Plain
// const: not used inside a vi.mock factory, so no vi.hoisted needed.
const RouterLinkStub = { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" };

const mountPage = () =>
  shallowMount(ForgotPassword, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  });

describe("ForgotPassword — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
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

  // ── (1) default mount: empty email form ────────────────────────────────────
  // The core guard: setup() runs (useRoute + useI18n + refs + the submit closure),
  // the signinLink computed evaluates via the RouterLink :to binding, and the whole
  // form template renders with an empty identifier — all without throwing.
  it("mounts the empty reset-request form without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Own-template anchors (the mocked t echoes the key):
    expect(wrapper.text()).toContain("forgotPassword.title"); // spotlight + card heading
    expect(wrapper.text()).toContain("forgotPassword.sendResetLink"); // submit CTA (not submitting)
    // Proves the signinLink computed evaluated and the RouterLink slot rendered:
    expect(wrapper.text()).toContain("forgotPassword.signInLink");
    // No fetch fires at mount — the reset POST is submit-only.
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  // ── (2) submitted → success confirmation shown ─────────────────────────────
  // Drives the submit() path: fill the identifier, submit the form, api.post
  // resolves with a detail message → the success alert (`v-if="message"`) renders.
  // This exercises the page's only real async branch and confirms it renders the
  // sent-confirmation state without throwing.
  it("shows the success confirmation after a submitted reset request", async () => {
    api.post.mockResolvedValueOnce({ data: { detail: "Check your inbox" } });

    wrapper = mountPage();
    await flushPromises();

    await wrapper.find("input").setValue("owner@example.com");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(wrapper.exists()).toBe(true);
    expect(api.post).toHaveBeenCalledWith(
      "/password-reset/request/",
      { identifier: "owner@example.com" }
    );
    // The success alert rendered the returned detail message.
    expect(wrapper.text()).toContain("Check your inbox");
    // Page is still intact (own heading still present).
    expect(wrapper.text()).toContain("forgotPassword.title");
  });
});
