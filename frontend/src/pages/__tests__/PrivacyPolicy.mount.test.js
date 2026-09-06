/**
 * Mount smoke test for PrivacyPolicy.vue (the static legal/privacy page, ~59 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, bad import) was never
 * caught by a test". Mounting the page runs its real setup() + first render — so
 * any such crash fails CI here instead of white-screening in production.
 *
 * WHAT THIS PAGE IS (verified by reading it): a genuinely STATIC legal page. Its
 * setup() has NO store, NO lib/api, NO onMounted, NO fetch, and NO useRoute/
 * useRouter. It only:
 *   - reads i18n `t` (destructured as { t } — the ONLY destructure)
 *   - computes supportEmail = import.meta.env.VITE_CONTACT_EMAIL || SUPPORT_EMAIL
 *   - builds sections = computed(() => [t(p1), t(p2), t(p3)]), rendered via v-for
 * There is no props/route/query/state axis to vary → ONE solid default-mount guard
 * is the complete test (see note at (1)).
 *
 * Pattern-faithful to pages/__tests__/NotFound.mount.test.js (the vi.hoisted
 * RouterLink pattern for an IMPORTED RouterLink) + DemoLanding.mount.test.js
 * (static-page structure), trimmed to exactly what this page imports:
 *   - shallowMount so the page's OWN setup() runs (the thing under test)
 *   - useI18n mocked to echo keys verbatim ({ t } is the only destructure)
 *   - vue-router mocked: the page does `import { RouterLink } from "vue-router"`,
 *     so RouterLink is a vi.hoisted stub. A plain module-scope const referenced in
 *     the hoisted vi.mock factory would hit the TDZ → the file collects "0 test".
 *     This page imports ONLY RouterLink from vue-router (no useRoute/useRouter), so
 *     the mock exports only RouterLink.
 *   - real pinia in beforeEach: defensive scaffolding only — the page touches NO
 *     store, but this keeps the harness faithful to the proven template.
 *
 * lib/brand (SUPPORT_EMAIL) is left REAL: it is a pure env-var-backed constant with
 * a static fallback (no side effects, no network). The page's supportEmail is
 * computed exactly as `VITE_CONTACT_EMAIL || SUPPORT_EMAIL`; asserting that same
 * value reached the render proves the real ../lib/brand import path resolved at setup.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// PrivacyPolicy does `import { RouterLink } from "vue-router"`.
// vi.hoisted: the vi.mock("vue-router") factory below is hoisted above the imports
// and runs during import evaluation — before a plain `const` in the file body would
// initialize — so referencing a plain const there hits the TDZ ("0 test" collection
// error). vi.hoisted makes the stub available to the hoisted factory. The page
// imports ONLY RouterLink from vue-router → the mock exports only RouterLink.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({ RouterLink: RouterLinkStub }));

// Real brand constant — the page's supportEmail resolves to it (no VITE_CONTACT_EMAIL
// in the test env) — so the mount assertion can confirm the real ../lib/brand import
// path resolved at setup and its value flowed to the rendered aside.
import { SUPPORT_EMAIL } from "../../lib/brand";
import PrivacyPolicy from "../PrivacyPolicy.vue";

const expectedSupportEmail = import.meta.env.VITE_CONTACT_EMAIL || SUPPORT_EMAIL;

const mountPage = () =>
  shallowMount(PrivacyPolicy, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  });

describe("PrivacyPolicy — mount smoke", () => {
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

  // ── (1) default mount — the complete white-screen guard ─────────────────────
  // setup() (the supportEmail + sections computeds) plus the whole template must
  // render without throwing. There is no props/route/store/state axis to vary on a
  // static legal page, so this single case is the complete crash guard.
  it("mounts without a setup() crash and renders its title + privacy sections", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // The <h1> heading (privacyPolicy.title) — own-template key, returned verbatim
    // by the mocked t → the hero header rendered. The crash-guard anchor.
    expect(text).toContain("privacyPolicy.title");
    // A section key (privacyPolicy.p1) proves the v-for over the `sections` computed
    // actually ran and rendered its items.
    expect(text).toContain("privacyPolicy.p1");
    // The real ../lib/brand constant reached the render (import path resolved at setup).
    expect(text).toContain(expectedSupportEmail);
  });
});
