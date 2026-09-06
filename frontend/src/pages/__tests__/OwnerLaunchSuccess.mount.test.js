/**
 * Mount smoke test for OwnerLaunchSuccess.vue (the post-onboarding "your menu is
 * live / still draft" success page — public storefront link, share message, next
 * actions; ~180 lines).
 *
 * WHY: this page had NO mount test. The app's recurring production bug class is
 * "a page white-screens on load because a setup()-time error (TDZ, undefined map
 * access, bad import) was never caught by a test". Mounting the page runs its real
 * <script setup> for real — the isPublished / tenantName computeds that read
 * tenant.meta, the menuUrl / menuHost computeds that read window.location, the
 * shareMessage computed, and useVocabulary()'s catalog — so any such crash fails
 * CI here instead of white-screening in production.
 *
 * Boundary (verified by reading the source, NOT assumed):
 *   - The page is PURELY STATIC: it has NO onMounted, NO watch, NO interval /
 *     observer / WebSocket, and — critically — NO lib/api import and NO fetch at
 *     mount. It reads everything from the TENANT STORE state (`tenant.meta`), so
 *     the loaded case seeds `useTenantStore().meta` DIRECTLY (real pinia), exactly
 *     like OwnerBilling / OwnerProfile. Because nothing fetches, there is
 *     deliberately NO lib/api mock (the page never imports it).
 *   - It imports NOTHING from vue-router (no useRoute / useRouter). <RouterLink>
 *     appears in the template purely as a GLOBAL component, so — like
 *     OwnerMenuBuilder / CustomerLeadPage / Menu — there is NO vue-router mock and
 *     NO vi.hoisted stub; a plain RouterLink stub in global.stubs (rendering its
 *     slot) is all that's needed.
 *   - useI18n is destructured as ONLY { t } (verified) → mocked to identity keys.
 *   - useVocabulary is left REAL: it only uses the mocked `t` + the real tenant
 *     store, and its `catalog` is null-safe (businessType falls back to
 *     "restaurant"). useToastStore is left real too (trivial store; toast.show is
 *     only called from the copy click-handlers, never at mount).
 *   - menuUrl / menuHost read window.location at render (via computeds); jsdom
 *     provides window.location, so no window stub is needed.
 *
 * localStorage.clear() in beforeEach is pure hygiene here (the page never touches
 * the staleCache), kept to match the proven mount-smoke template.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// The page destructures ONLY { t } from useI18n (verified). Identity keys.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

import { useTenantStore } from "../../stores/tenant";
import OwnerLaunchSuccess from "../OwnerLaunchSuccess.vue";

// RouterLink is a GLOBAL component here (the page imports nothing from vue-router),
// so shallowMount cannot auto-resolve it. A plain stub that renders its default
// slot keeps the CTA link text in the rendered output and silences the `to` warn.
const mountPage = () =>
  shallowMount(OwnerLaunchSuccess, {
    global: {
      stubs: {
        RouterLink: { name: "RouterLink", props: ["to"], template: "<a><slot /></a>" },
      },
    },
  });

describe("OwnerLaunchSuccess — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // Pure hygiene: the page never reads the localStorage-backed staleCache, but
    // clearing keeps one test's store state from ever bleeding into the next.
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    // No intervals / observers to leak; unmount for clean teardown, matching the
    // other mount-smoke tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) default mount: no tenant meta (→ DRAFT state) ────────────────────────
  // The core guard: setup() (the isPublished / tenantName / menuUrl / menuHost /
  // shareMessage computeds + useVocabulary's catalog) and the whole template must
  // render with a null meta and not throw. isPublished is false (optional-chained
  // meta is null) → the draft title renders and the isPublished-only share card is
  // hidden; tenantName falls back to t("ownerLaunchSuccess.defaultRestaurantName").
  it("mounts with no tenant meta (draft state) without a setup() crash", async () => {
    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Always-rendered own-template anchors — the crash-guard anchors.
    expect(wrapper.text()).toContain("ownerLaunchSuccess.launch"); // header chip
    expect(wrapper.text()).toContain("ownerLaunchSuccess.nextActions"); // actions kicker
    // Not published → the DRAFT title branch renders.
    expect(wrapper.text()).toContain("ownerLaunchSuccess.draftTitle");
    // tenantName fell back safely (null meta) to the default-name key.
    expect(wrapper.text()).toContain("ownerLaunchSuccess.defaultRestaurantName");
  });

  // ── (2) loaded + published: real restaurant name + share card ────────────────
  // Drives the published branch that only renders with real data: the isPublished
  // computed (meta.profile.is_menu_published === true) flips the title to liveTitle
  // AND renders the isPublished-only "ready-to-share message" card (shareMessage
  // computed). tenantName resolves to the real restaurant name from the store.
  // The page never fetches at mount, so seed the store state directly BEFORE mount.
  it("mounts a loaded, published menu (restaurant name + share card) without a crash", async () => {
    useTenantStore().meta = {
      name: "Chez Test",
      slug: "chez-test",
      profile: {
        is_menu_published: true,
        restaurant_name: "Chez Test",
        business_type: "restaurant",
      },
    };

    expect(() => {
      wrapper = mountPage();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Loaded restaurant name from the page's own template (tenantName computed).
    expect(wrapper.text()).toContain("Chez Test");
    // Published → the LIVE title branch renders.
    expect(wrapper.text()).toContain("ownerLaunchSuccess.liveTitle");
    // Published-only share-message card rendered (v-if="isPublished").
    expect(wrapper.text()).toContain("ownerLaunchSuccess.shareMessageTitle");
  });
});
