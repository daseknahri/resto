/**
 * Mount smoke test for TermsOfService.vue (the static Terms of Service legal page, ~69 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined access, bad import) was never caught
 * by a test". Mounting the page runs its real setup() + first render — so any such
 * crash fails CI here instead of white-screening in production.
 *
 * WHAT THIS PAGE IS (verified by reading it): a genuinely STATIC legal page. Its
 * setup() only:
 *   - destructures `{ t }` from useI18n (t is the ONLY destructure),
 *   - reads a pure brand constant (SUPPORT_EMAIL, via import.meta.env fallback),
 *   - builds `sections = computed(() => [t("termsOfService.p1"), .p2, .p3])`,
 *     rendered via a v-for.
 * There is NO store, NO lib/api, NO onMounted, NO fetch, and NO useRoute/useRouter.
 * The ONLY vue-router import is `{ RouterLink }` (used in the /get-started CTA).
 * So there is no loaded-state axis to vary — ONE solid default-mount guard is the
 * complete test for this page (see note at (1)).
 *
 * Pattern-faithful to pages/__tests__/NotFound.mount.test.js (the vi.hoisted
 * RouterLink stub for an IMPORTED RouterLink) + pages/__tests__/DemoLanding.mount.test.js
 * (single static-page case), trimmed to what this page actually imports:
 *   - shallowMount runs the page's OWN setup() (the thing under test)
 *   - useI18n mocked to echo keys ({ t } only — the page destructures just t)
 *   - real pinia (setActivePinia(createPinia())): the page touches NO store, but this
 *     keeps the harness faithful to the proven template and ready if one is added.
 *
 * lib/brand (SUPPORT_EMAIL) is left REAL: it is a pure env-var-backed constant with a
 * static fallback (no side effects, no network), and the page importing it means the
 * whole file would fail to collect if that import path did not resolve at setup.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// TermsOfService imports ONLY { RouterLink } from 'vue-router' (no useRoute/useRouter).
// vi.hoisted: the vi.mock('vue-router') factory below is hoisted above the imports and
// runs during import evaluation — before a plain `const` in the file body would
// initialize — so referencing a plain const there hits the TDZ ("0 test" collection
// error). vi.hoisted makes the stub available to the hoisted factory. The mock only
// needs to export RouterLink because that is the sole vue-router import.
const RouterLinkStub = vi.hoisted(() => ({ name: "RouterLink", props: ["to"], template: "<a><slot /></a>" }));
vi.mock("vue-router", () => ({ RouterLink: RouterLinkStub }));

import TermsOfService from "../TermsOfService.vue";

const mountPage = () =>
  shallowMount(TermsOfService, {
    global: {
      stubs: {
        RouterLink: RouterLinkStub,
      },
    },
  });

describe("TermsOfService — mount smoke", () => {
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
  // setup() (the `sections` computed) + the whole template must render without
  // throwing. There is no state variation on this static legal page, so this
  // single case is the complete crash guard.
  it("mounts without a setup() crash and renders the title + the v-for sections", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // Own-template <h1> heading (termsOfService.title) — the crash-guard anchor,
    // returned verbatim by the mocked t.
    expect(text).toContain("termsOfService.title");
    // A section key rendered → the v-for over the `sections` computed actually ran.
    expect(text).toContain("termsOfService.p1");
  });
});
