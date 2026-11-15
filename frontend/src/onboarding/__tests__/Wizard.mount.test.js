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
  // shared canonical extractor (added to lib/api; mock returns the fallback)
  extractApiErrorMessage: (err, fallback = "") => fallback,
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
// ── S1-F (A3-01 / A3-08): StepBrand + StepTheme mount tests ─────────────────
// Appended by S1-F; the base file above is untouched. The two step components
// are mounted for real (mount, not shallowMount) because both gaps live in
// their own template/script: the Save button's :disabled binding and the hours
// validation inside saveAndNext. The Wizard shell tests above keep their mocks;
// the three mocks below are hoisted by vitest, so they apply file-wide, but
// none of them touches a module the shell tests use (Wizard imports neither
// onboardingApi, useTranslate nor templateCatalog).
vi.mock("../../lib/onboardingApi", () => ({
  profileApi: {
    get: vi.fn(),
    save: vi.fn(() => Promise.resolve({})),
  },
  uploadApi: {
    image: vi.fn(() => Promise.resolve({ url: "" })),
    removeImage: vi.fn(() => Promise.resolve({})),
  },
}));

// StepBrand destructures { translating, translateError, translateField } from
// useTranslate(); the real composable POSTs /translate/ — mocked out, the
// translate buttons are never clicked here.
vi.mock("../../composables/useTranslate", () => ({
  useTranslate: () => ({
    translating: {},
    translateError: { value: "" },
    translateField: vi.fn(() => Promise.resolve(null)),
  }),
}));

// StepTheme loads the template-palette catalog on mount; the real fetch hits
// GET /owner/apply-template/ — resolve the empty list so THEME_PRESETS apply.
vi.mock("../../lib/templateCatalog", () => ({
  fetchTemplateSummaries: () => Promise.resolve([]),
}));

import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import StepBrand from "../StepBrand.vue";
import StepTheme from "../StepTheme.vue";
import { profileApi } from "../../lib/onboardingApi";
import { useToastStore } from "../../stores/toast";
import { useThemeStore } from "../../stores/theme";

// Profile GET fixture: Monday is a bar night (18:00-02:00, overnight window).
const BRAND_PROFILE = {
  tagline: "Our place",
  description: "",
  business_hours_schedule: {
    mon: { enabled: true, open: "18:00", close: "02:00" },
  },
  language: "en",
};

// The Save button renders "common.saveAndNext" (identity-t mock) in both steps
// when not standalone.
const findSaveButton = (wrapper) =>
  wrapper.findAll("button").find((b) => b.text().includes("common.saveAndNext"));

describe("StepBrand / StepTheme — S1-F (A3-01 load-fail guard, A3-08 overnight hours)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    useTenantStore().$patch({ meta: { slug: "demo", profile: { is_menu_published: false } } });
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountStepBrand = () => mount(StepBrand, { props: { standalone: false } });
  const mountStepTheme = () =>
    mount(StepTheme, {
      props: { standalone: false },
      global: { stubs: { TemplatePickerModal: true } },
    });

  // ── A3-01 StepBrand: failed load ──────────────────────────────────────────
  // The form keeps its empty defaults after a failed GET; Save must be disabled
  // and, even if a click is dispatched at the disabled button, the saveAndNext
  // guard must hold — no PUT of the default form over the stored profile.
  it("A3-01 StepBrand: a failed profile load disables Save and never saves the default form", async () => {
    profileApi.get.mockRejectedValueOnce(new Error("offline"));
    wrapper = mountStepBrand();
    await flushPromises();
    await nextTick();

    expect(wrapper.text()).toContain("stepBrand.statusLoadFailed");
    const saveBtn = findSaveButton(wrapper);
    expect(saveBtn.attributes("disabled")).toBeDefined();
    expect(wrapper.findAll("button").some((b) => b.text().includes("common.retry"))).toBe(true);
    await saveBtn.trigger("click");
    await flushPromises();
    expect(profileApi.save).not.toHaveBeenCalled();
  });

  it("A3-01 StepBrand: Retry re-loads the profile and re-enables Save", async () => {
    profileApi.get.mockRejectedValueOnce(new Error("offline"));
    wrapper = mountStepBrand();
    await flushPromises();
    await nextTick();
    expect(findSaveButton(wrapper).attributes("disabled")).toBeDefined();

    profileApi.get.mockResolvedValue({ ...BRAND_PROFILE });
    const retryBtn = wrapper.findAll("button").find((b) => b.text().includes("common.retry"));
    await retryBtn.trigger("click");
    await flushPromises();
    await nextTick();

    expect(findSaveButton(wrapper).attributes("disabled")).toBeUndefined();
    expect(wrapper.text()).not.toContain("stepBrand.statusLoadFailed");
  });

  // ── A3-08 StepBrand: overnight windows ────────────────────────────────────
  it("A3-08 StepBrand: an overnight window (18:00-02:00) saves", async () => {
    profileApi.get.mockResolvedValue({ ...BRAND_PROFILE });
    wrapper = mountStepBrand();
    await flushPromises();
    await nextTick();

    expect(findSaveButton(wrapper).attributes("disabled")).toBeUndefined();
    await findSaveButton(wrapper).trigger("click");
    await flushPromises();

    expect(profileApi.save).toHaveBeenCalledTimes(1);
    const payload = profileApi.save.mock.calls[0][0];
    expect(payload.business_hours_schedule.mon).toEqual({ enabled: true, open: "18:00", close: "02:00" });
  });

  it("A3-08 StepBrand: open == close (09:00-09:00) is rejected and never saves", async () => {
    profileApi.get.mockResolvedValue({
      ...BRAND_PROFILE,
      business_hours_schedule: { mon: { enabled: true, open: "09:00", close: "09:00" } },
    });
    wrapper = mountStepBrand();
    await flushPromises();
    await nextTick();

    await findSaveButton(wrapper).trigger("click");
    await flushPromises();

    expect(profileApi.save).not.toHaveBeenCalled();
    expect(useToastStore().message).toContain("stepBrand.businessHoursTimeEqual");
  });

  // ── A3-01 StepTheme: failed load ──────────────────────────────────────────
  it("A3-01 StepTheme: a failed profile load disables Save and never saves the default theme", async () => {
    profileApi.get.mockRejectedValueOnce(new Error("offline"));
    wrapper = mountStepTheme();
    await flushPromises();
    await nextTick();

    expect(wrapper.text()).toContain("common.loadFailed");
    const saveBtn = findSaveButton(wrapper);
    expect(saveBtn.attributes("disabled")).toBeDefined();
    await saveBtn.trigger("click");
    await flushPromises();
    expect(profileApi.save).not.toHaveBeenCalled();
  });

  it("A3-01 StepTheme: a loaded profile enables Save and saving persists the theme", async () => {
    profileApi.get.mockResolvedValue({
      primary_color: "#123456",
      secondary_color: "#654321",
      logo_url: "",
      hero_url: "",
    });
    wrapper = mountStepTheme();
    await flushPromises();
    await nextTick();

    expect(findSaveButton(wrapper).attributes("disabled")).toBeUndefined();
    await findSaveButton(wrapper).trigger("click");
    await flushPromises();

    expect(profileApi.save).toHaveBeenCalledTimes(1);
    const payload = profileApi.save.mock.calls[0][0];
    expect(payload.primary_color).toBe("#123456");
    expect(payload.secondary_color).toBe("#654321");
    expect(useThemeStore().primary).toBe("#123456");
  });
});
