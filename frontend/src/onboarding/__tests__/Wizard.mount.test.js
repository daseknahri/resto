/**
 * Mount smoke test for onboarding/Wizard.vue (the OWNER ONBOARDING wizard, ~337
 * lines — the activation funnel the router lazy-loads at /owner/onboarding).
 *
 * WHY: the app's recurring production bug class is "a route component
 * white-screens on load because a setup()-time error (TDZ, undefined access, a
 * missing composable member, an unguarded browser API) was never caught by a
 * test". Wizard.vue lives in src/onboarding/ (not src/pages/) but is a router
 * target all the same, so it's exposed to the identical bug class — and it's
 * especially exposed:
 *   - an ASYNC onMounted that (conditionally) awaits tenant.fetchMeta(), then
 *     branches on is_menu_published — either redirecting a published tenant away
 *     via router.replace({ name: "owner-home" }) OR restoring the saved step from
 *     localStorage (restoreStep());
 *   - a SECOND onMounted that wires a `beforeunload` listener (removed onUnmounted);
 *   - an onBeforeRouteLeave guard REGISTERED at setup (calling it needs a real fn);
 *   - a 6-step nav whose stepTitle() reads vocabulary refs (groupSingular /
 *     itemSingular .value) for the categories & dishes steps on every render.
 * shallowMount runs Wizard.vue's real setup() + both onMounted hooks while
 * auto-stubbing its heavy Step* children, so a crash in any of that fails CI here
 * instead of white-screening the onboarding flow.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js (async onMounted +
 * real pinia tenant store seeded via $patch to control the onMounted branch +
 * defensive lib/api mock + localStorage-first reset + unmount-in-afterEach) and
 * Menu.mount.test.js (composable mocks):
 *   - shallowMount (auto-stubs the 6 Step* children rendered via <component :is>)
 *   - real pinia (tenant store runs for real; meta is SEEDED before mount so
 *     `!tenant.meta` is false — no fetchMeta network — and the branch is chosen)
 *   - useI18n / useConfirmModal / useVocabulary / vue-router mocked; lib/api
 *     mocked defensively so any store action that slips through stays hermetic
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Wizard destructures EXACTLY { t } from useI18n(). The mocked `t` echoes its key
// verbatim (param-less) or as `key({...})` (with params), so the page's own
// template keys are assertable by substring.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// Wizard destructures { confirm } from useConfirmModal(); it's used ONLY inside the
// onBeforeRouteLeave guard (never at mount). Resolve true defensively.
vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({ confirm: vi.fn(() => Promise.resolve(true)) }),
}));

// Wizard destructures { catalog, groupSingular, itemSingular } from useVocabulary()
// (the real composable returns computeds). `catalog` is only spread into a t() param
// in the template (never .value'd), but groupSingular/itemSingular ARE read as
// `.value` in stepTitle() — which runs at mount for the categories & dishes nav
// items — so those two MUST be ref-like ({ value }).
vi.mock("../../composables/useVocabulary", () => ({
  useVocabulary: () => ({
    catalog: {},
    groupSingular: { value: "category" },
    itemSingular: { value: "dish" },
  }),
}));

// Wizard imports { onBeforeRouteLeave, useRouter } from vue-router.
// - onBeforeRouteLeave is CALLED at setup → the mock MUST supply a callable no-op
//   (vi.fn()), or setup() throws "onBeforeRouteLeave is not a function".
// - router.replace is invoked at mount on the published re-entry branch and is the
//   SAME spy the published-case test asserts on, so it must be vi.hoisted:
//   referenced inside the hoisted vi.mock factory AND in the test body (trap #1).
const routerReplaceSpy = vi.hoisted(() => vi.fn());
vi.mock("vue-router", () => ({
  useRouter: () => ({ push: vi.fn(), replace: routerReplaceSpy }),
  onBeforeRouteLeave: vi.fn(),
}));

// Defensive: Wizard itself never imports lib/api, but the real tenant store does.
// Seeding tenant.meta means fetchMeta() is skipped entirely; this only keeps any
// slipped-through store action hermetic (no real network).
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import Wizard from "../Wizard.vue";
import { useTenantStore } from "../../stores/tenant";

const mountWizard = () =>
  shallowMount(Wizard, {
    global: {
      stubs: {
        // Defensive: render the dynamic step child (already stubbed by shallowMount)
        // through KeepAlive's slot without its single-child constraint.
        KeepAlive: { template: "<slot />" },
      },
    },
  });

describe("Wizard (owner onboarding) — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // localStorage FIRST: restoreStep() reads resto:onboarding-step:v2:<slug>, so a
    // leaked write from a prior test would change which step this mount restores.
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    // onMounted adds a `beforeunload` listener; unmount runs onUnmounted →
    // removeEventListener so no listener leaks between tests.
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) unpublished tenant: the core setup()/onMounted crash guard ─────────
  // Seed meta with is_menu_published:false → onMounted skips fetchMeta (meta is
  // present), sets published=false, and falls through to restoreStep() (step 1,
  // since localStorage was cleared). The whole wizard shell + 6-step nav (whose
  // stepTitle reads the vocabulary refs) must render without throwing.
  it("mounts an unpublished tenant (renders step 1 of the wizard) without a setup() crash", async () => {
    const tenant = useTenantStore();
    tenant.$patch({ meta: { slug: "demo", profile: { is_menu_published: false } } });

    // The white-screen bug class throws synchronously inside setup(), so mount()
    // itself would throw — this is the guard.
    expect(() => {
      wrapper = mountWizard();
    }).not.toThrow();

    await flushPromises();
    await flushPromises(); // drain the async onMounted (restoreStep path)

    expect(wrapper.exists()).toBe(true);
    // Always-rendered header + progress strip — the crash-guard anchors.
    expect(wrapper.text()).toContain("onboardingWizard.title");
    expect(wrapper.text()).toContain("onboardingWizard.stepProgress");
    // Unpublished → the Draft chip (not Published) — confirms the branch rendered.
    expect(wrapper.text()).toContain("onboardingWizard.draft");
    // No redirect on the unpublished path.
    expect(routerReplaceSpy).not.toHaveBeenCalled();
  });

  // ── (2) published tenant: the re-entry redirect path ──────────────────────
  // Seed meta with is_menu_published:true → onMounted sets published=true and, with
  // meta present, calls router.replace({ name: "owner-home" }) then returns (skips
  // restoreStep). Exercises the distinct published-onMounted branch end to end.
  it("redirects a published tenant to owner-home from onMounted without a crash", async () => {
    const tenant = useTenantStore();
    tenant.$patch({ meta: { slug: "demo", profile: { is_menu_published: true } } });

    expect(() => {
      wrapper = mountWizard();
    }).not.toThrow();

    await flushPromises();
    await flushPromises(); // drain the async onMounted (await router.replace)

    expect(wrapper.exists()).toBe(true);
    // The re-entry guard fired with the exact target route.
    expect(routerReplaceSpy).toHaveBeenCalledWith({ name: "owner-home" });
    // published=true → the Published chip rendered (the branch actually ran).
    expect(wrapper.text()).toContain("onboardingWizard.published");
  });
});
