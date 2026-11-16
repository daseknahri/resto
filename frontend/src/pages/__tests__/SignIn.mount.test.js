/**
 * Mount smoke test for SignIn.vue (the owner/staff credentials sign-in page, ~485 lines).
 *
 * WHY: this page had NO mount test — only a helper-function test
 * (signInSanitizeNext.test.js) that imports the exported `sanitizeNext`. Its
 * component setup() had NEVER been mounted. The app's recurring production bug
 * class is "a page white-screens on load because a setup()-time error (TDZ,
 * undefined access, bad import) was never caught by a test". Mounting the page
 * runs its real setup() — useRoute()/useRouter()/useSessionStore()/useI18n()
 * plus the computed graph (sessionExpired, activateLink, forgotPasswordLink)
 * the template forces to evaluate — so any such crash fails CI here instead of
 * in production.
 *
 * WHAT THIS PAGE IS (verified by reading it): the owner/staff sign-in page. NO
 * onMounted, NO fetch at mount, NO Leaflet/observers. Three template branches
 * (mfaRequired / forcePasswordChangeRequired / else) all default false, so a
 * default mount renders the "normal sign-in step". The two watches (mfaRequired,
 * useBackupCode) are NOT immediate, so they don't fire at mount.
 *
 * Pattern-faithful to pages/__tests__/Unauthorized.mount.test.js:
 *   - shallowMount runs the page's own setup() (the thing under test)
 *   - real pinia (the session store runs for real; loading defaults false)
 *   - useI18n mocked to echo keys verbatim ({ t } only — the page destructures
 *     exactly { t }) so assertions target the exact keys the page's OWN template
 *     renders. The EN values collide ("Sign in" is both signIn.title and
 *     common.signIn), so echoing keys is what disambiguates them.
 *   - vue-router mocked (the page imports { useRoute, useRouter })
 *   - lib/api mocked defensively (imported but only used in submitForcePasswordChange,
 *     never at mount) — keeps the test (and the session store, which also imports
 *     lib/api) hermetic
 *   - lib/runtimeHost left REAL (pure; imported but only used in a submit handler)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// The page imports `api` from ../lib/api — used ONLY in the submitForcePasswordChange
// handler, never at mount. Mock it defensively so importing the page (and the
// session store, which also imports lib/api) stays hermetic and side-effect free.
vi.mock("../../lib/api", () => ({
  // shared canonical extractor (added to lib/api; mock returns the fallback)
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: { post: vi.fn(() => Promise.resolve({ data: {} })) },
}));

// vue-router: the page imports { useRoute, useRouter }. route.query drives the
// sessionExpired / activateLink / forgotPasswordLink computeds; router.push is
// only touched by post-login handlers, never at mount. `routeState` is hoisted so
// the (hoisted) vi.mock factory can read it without hitting the TDZ — each test
// sets routeState.query BEFORE mount, and useRoute() reads it lazily at mount.
// Default {} = the normal sign-in step (no session-expired notice).
const routeState = vi.hoisted(() => ({ query: {} }));
vi.mock("vue-router", () => ({
  useRoute: () => ({ query: routeState.query }),
  useRouter: () => ({ push: vi.fn() }),
}));

import SignIn from "../SignIn.vue";

// <RouterLink> is a global (un-imported) component here → pass-through stub so the
// activation / reset / customer-hint links render their slot text. It is NOT
// referenced inside a vi.mock factory (it lives in global.stubs), so no vi.hoisted
// is needed for it.
const mountPage = () =>
  shallowMount(SignIn, {
    global: {
      stubs: {
        RouterLink: { props: ["to"], template: "<a><slot /></a>" },
      },
    },
  });

describe("SignIn — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    routeState.query = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) default → normal sign-in step ─────────────────────────────────────
  // The core guard: setup() + the computed graph + the "else" (normal sign-in)
  // branch must render and not throw. Empty route.query → sessionExpired false,
  // so the amber session-expired notice is absent; session.loading defaults
  // false so the submit button shows common.signIn (not signIn.signingIn).
  it("mounts the normal sign-in step without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Own-template heading — the <h1> in the else branch.
    expect(wrapper.text()).toContain("signIn.title");
    // Submit-button label (session.loading defaults false → common.signIn).
    expect(wrapper.text()).toContain("common.signIn");
    // Empty query → the session-expired notice is NOT rendered.
    expect(wrapper.text()).not.toContain("signIn.sessionExpired");
  });

  // ── (2) session-expired variant ───────────────────────────────────────────
  // api.js redirects here with ?expired=1 after a 401. Seeding routeState.query
  // flips the sessionExpired computed true → the amber notice renders. setup()
  // must still not throw and the heading must still be present.
  it("renders the session-expired notice when route.query.expired === '1'", async () => {
    routeState.query = { expired: "1" };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // The amber session-expired notice now renders (own template, v-if="sessionExpired").
    expect(wrapper.text()).toContain("signIn.sessionExpired");
    // The normal sign-in heading is still present.
    expect(wrapper.text()).toContain("signIn.title");
  });
});

// ── C-20: forced password change enforces the 8-character minimum ──────────
// The forced-change step is reached via completeSignIn() when the signed-in
// user has must_change_password; the test drives it by flipping the exposed
// step ref (sanctioned wrapper.vm pattern) and awaiting nextTick before
// touching the form, so the :disabled bindings have settled.
import api from "../../lib/api";

describe("SignIn — C-20 forced password change length check", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    routeState.query = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountForceStep = async () => {
    wrapper = mountPage();
    await flushPromises();
    wrapper.vm.forcePasswordChangeRequired = true;
    await wrapper.vm.$nextTick();
    await flushPromises();
    expect(wrapper.text()).toContain("forcePasswordChange.title");
    return wrapper.findAll('input[type="password"]');
  };

  const fillForceForm = async (inputs, current, next, confirm) => {
    await inputs[0].setValue(current);
    await inputs[1].setValue(next);
    await inputs[2].setValue(confirm);
    await wrapper.find("form").trigger("submit");
    await flushPromises();
  };

  it("shows the length hint on the new-password field", async () => {
    await mountForceStep();
    expect(wrapper.text()).toContain("forcePasswordChange.passwordHint");
  });

  it("blocks a new password under 8 chars client-side (no API call)", async () => {
    const inputs = await mountForceStep();
    expect(inputs).toHaveLength(3);
    await fillForceForm(inputs, "old-temp-pw", "short", "short");
    expect(wrapper.text()).toContain("forcePasswordChange.passwordTooShort");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("lets an 8-char new password through to the change-password endpoint", async () => {
    const inputs = await mountForceStep();
    await fillForceForm(inputs, "old-temp-pw", "12345678", "12345678");
    expect(wrapper.text()).not.toContain("forcePasswordChange.passwordTooShort");
    expect(api.post).toHaveBeenCalledWith("/staff/change-password/", {
      current_password: "old-temp-pw",
      new_password: "12345678",
    });
  });
});
