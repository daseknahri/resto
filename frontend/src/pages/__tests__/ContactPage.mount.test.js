/**
 * Mount smoke test for ContactPage.vue (the static support/contact page, ~89 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, bad import) was never
 * caught by a test". Mounting the page runs its real setup() + first render — so
 * any such crash fails CI here instead of white-screening in production.
 *
 * WHAT THIS PAGE IS (verified by reading the whole file incl. template): a
 * genuinely STATIC support page. Its setup() has NO store, NO lib/api, NO
 * onMounted, NO fetch, and NO useRoute/useRouter. It only:
 *   - reads i18n `t` (destructured as { t } — the ONLY destructure)
 *   - computes supportEmail = (import.meta.env.VITE_CONTACT_EMAIL || SUPPORT_EMAIL).trim()
 *   - computes supportPhone / supportPhoneLabel / whatsappUrl from import.meta.env
 *     (VITE_CONTACT_PHONE / VITE_CONTACT_MESSAGE) — pure string building, no network
 * There is no props/route/query/store axis to vary → ONE solid default-mount guard
 * is the complete test (see note at (1)).
 *
 * NO ROUTER: unlike its sibling PrivacyPolicy.vue, ContactPage does NOT
 * `import { RouterLink }` and its template uses ONLY plain <a href> anchors
 * (mailto: / https://wa.me/…) — no <RouterLink>, no child components at all. So
 * there is no vue-router mock and nothing to stub; full `mount` renders the real
 * template exactly as `shallowMount` would (identical with zero children), and is
 * the stronger crash guard.
 *
 * Pattern-faithful to pages/__tests__/PrivacyPolicy.mount.test.js (the nearest
 * sibling — same `VITE_CONTACT_EMAIL || SUPPORT_EMAIL` idiom and static-page shape),
 * trimmed to exactly what this page imports:
 *   - useI18n mocked to echo keys verbatim ({ t } is the only destructure) so the
 *     assertions target the exact i18n keys the page's OWN template renders
 *   - real pinia in beforeEach: defensive scaffolding only — the page touches NO
 *     store, but this keeps the harness faithful to the proven template.
 *
 * WHATSAPP BRANCH: whatsappUrl returns "#" when no phone is configured. The test
 * env sets no VITE_CONTACT_PHONE (only .env.example exists, and Vite never loads
 * it), so the default mount already exercises the whatsappUrl === "#" ("not
 * configured") branch — the branch that actually runs in CI. The alternate
 * `https://wa.me/…` path is pure side-effect-free string building, so a second
 * env-stubbed case would add no crash-guard value → ONE case is sufficient.
 *
 * lib/brand (SUPPORT_EMAIL) is left REAL: it is a pure env-var-backed constant with
 * a static fallback (no side effects, no network). The page's supportEmail is
 * computed exactly as `(VITE_CONTACT_EMAIL || SUPPORT_EMAIL).trim()`; asserting that
 * same value reached the render proves the real ../lib/brand import path resolved at
 * setup and its value flowed to the rendered card.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// Real brand constant — the page's supportEmail resolves to it (no VITE_CONTACT_EMAIL
// in the test env) — so the mount assertion can confirm the real ../lib/brand import
// path resolved at setup and its value flowed to the rendered email card. Computed the
// same way the page does (incl. .trim()) so the assertion holds regardless of env.
import { SUPPORT_EMAIL } from "../../lib/brand";
import ContactPage from "../ContactPage.vue";

const expectedSupportEmail = (import.meta.env.VITE_CONTACT_EMAIL || SUPPORT_EMAIL).trim();

const mountPage = () => mount(ContactPage);

describe("ContactPage — mount smoke", () => {
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
  // setup() (the supportEmail / supportPhone / whatsappUrl computeds) plus the whole
  // template must render without throwing. There is no props/route/store/state axis
  // to vary on a static support page, so this single case is the complete crash guard.
  it("mounts without a setup() crash and renders its title, sections + support email", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);

    const text = wrapper.text();
    // The <h1 id="contact-page-title"> heading (contactPage.title) — own-template key,
    // returned verbatim by the mocked t → the hero header rendered. The crash anchor.
    expect(text).toContain("contactPage.title");
    // The top chip (contactPage.kicker) proves the hero header block rendered.
    expect(text).toContain("contactPage.kicker");
    // A key from the LAST block (contactPage.fasterSupport, the command-deck <h2>)
    // proves the whole template rendered top-to-bottom, not just the header.
    expect(text).toContain("contactPage.fasterSupport");
    // The real ../lib/brand constant reached the render (import path resolved at setup).
    expect(text).toContain(expectedSupportEmail);
  });
});
