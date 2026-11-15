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
// Partial mock (coordinator merge fix): S1-F needs profileApi/uploadApi stubbed,
// but S1-H's tests need the REAL superCategoryApi/categoryApi/dishApi — they drive
// them through the mocked lib/api per test. Spreading the real module keeps both;
// a whole-module stub (profileApi/uploadApi only) left superCategoryApi undefined
// and broke all 8 S1-H tests.
vi.mock("../../lib/onboardingApi", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    profileApi: {
      // Delegate to the REAL get by default: S1-H's A3-09 tests seed the profile
      // through the mocked lib/api (api.get "/profile/"), and StepPublish loads
      // via profileApi.get(). A bare vi.fn() returns undefined, so the seeded
      // tagline never reached the component. S1-F's tests override this per test
      // with mockResolvedValue/mockRejectedValueOnce as before.
      get: vi.fn((...args) => actual.profileApi.get(...args)),
      save: vi.fn(() => Promise.resolve({})),
    },
    uploadApi: {
      image: vi.fn(() => Promise.resolve({ url: "" })),
      removeImage: vi.fn(() => Promise.resolve({})),
    },
  };
});

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


// ── Run 8 S1-H (A3-04, A3-05, A3-07, A3-09) — appended 2026-11-15 ──────────
// The two base Wizard mount-smoke tests above are untouched; everything below
// this line is new. 10 tests: A3-04 upsert payload (2), A3-05 delete + A3-04
// component round-trip (4), A3-07 save-and-exit (2), A3-09 publish gate (2).
//
// Mock notes — every vi.mock below is hoisted by Vitest, so it applies
// file-wide. Each factory is either DISJOINT from the base file's factories
// (new paths only) or a SUPERSET of one, so the base tests keep passing:
// - ../../lib/slug, ../../i18n/translate, ../../lib/staleCache: the real
//   lib/onboardingApi's imports, mocked so the A3-04 unit tests can assert on
//   the exact payload superCategoryApi.upsert sends (and so mounting
//   StepSuperCategories / StepPublish stays hermetic).
// - ../../lib/menuVisibility, ../../lib/analytics: StepPublish's imports.
// - ../../composables/useFocusTrap, ../../i18n/config: StepSuperCategories'
//   imports (the mock keeps the exact shape the component reads).
// - ../../composables/useVocabulary: RE-MOCKED as a superset of the base
//   factory — the same groupSingular / itemSingular / catalog values the
//   Wizard needs, plus the isShop / groupPlural / itemPlural StepPublish
//   reads. Vitest applies the LAST factory registered for a path; if that
//   ever changed, the StepPublish tests below would fail on the missing keys
//   while the base tests still pass — split them into a second file then
//   (they are one delimited block).
// - ../../lib/api is NOT re-mocked: the base factory stands, and each test
//   below assigns api.get / post / put / delete per-test onto the mocked
//   default export (the object is shared and mutable).
// - The base useConfirmModal mock (confirm resolves true) stands: the delete
//   tests exercise the proceed path. The cancel path (confirm resolves false)
//   cannot be flipped through that mock, so it is covered by code inspection
//   only — see REPORT.md.

vi.mock("../../lib/slug", () => ({
  slugify: (v) =>
    String(v || "item").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "item",
}));
vi.mock("../../i18n/translate", () => ({ translate: (k, fallback) => fallback || k }));
vi.mock("../../lib/staleCache", () => ({ bustCache: vi.fn() }));
vi.mock("../../lib/menuVisibility", () => ({
  countCustomerVisible: () => ({ categories: 2, dishes: 5 }),
}));
vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));
vi.mock("../../composables/useFocusTrap", () => ({ useFocusTrap: vi.fn() }));
vi.mock("../../i18n/config", () => ({
  DEFAULT_LOCALE: "en",
  LOCALE_OPTIONS: [
    { code: "en", label: "English", nativeLabel: "EN", dir: "ltr" },
    { code: "fr", label: "French", nativeLabel: "FR", dir: "ltr" },
    { code: "ar", label: "Arabic", nativeLabel: "AR", dir: "rtl" },
  ],
  normalizeLocale: (v) => {
    const p = String(v || "en").trim().toLowerCase().split(/[-_]/)[0];
    return ["en", "fr", "ar"].includes(p) ? p : "en";
  },
  getLocaleOption: () => ({ code: "en", label: "English", nativeLabel: "EN", dir: "ltr" }),
  getLocaleDirection: () => "ltr",
  detectBrowserLocale: () => "en",
}));
// Real refs (coordinator merge fix): StepPublish's template calls
// groupPlural.toLowerCase() / itemPlural.toLowerCase() and v-if="!isShop",
// which rely on <script setup> ref auto-unwrapping. Plain { value } objects
// are NOT unwrapped in templates, so the mock returned an object with no
// toLowerCase and both A3-09 tests crashed. The Wizard reads .value in script,
// which real refs also satisfy.
vi.mock("../../composables/useVocabulary", async () => {
  const { ref } = await import("vue");
  return {
    useVocabulary: () => ({
      catalog: {},
      groupSingular: ref("category"),
      itemSingular: ref("dish"),
      isShop: ref(false),
      groupPlural: ref("Categories"),
      itemPlural: ref("Dishes"),
    }),
  };
});

import api from "../../lib/api";
import { superCategoryApi } from "../../lib/onboardingApi";
import StepSuperCategories from "../StepSuperCategories.vue";
import StepPublish from "../StepPublish.vue";

// ── A3-04 — superCategoryApi.upsert keeps description + cover image ─────────
// Before the fix the whitelist payload had no description / description_i18n /
// image_url, so editor edits were silently discarded on save and reverted on
// reload. These tests assert on the exact payload the API layer sends.
describe("S1-H A3-04 — superCategoryApi.upsert keeps description + image", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    api.get = vi.fn(() => Promise.resolve({ data: {} }));
    api.post = vi.fn((url, payload) =>
      Promise.resolve({ data: { id: 9, slug: "mains", category_count: 0, ...payload } })
    );
    api.put = vi.fn((url, payload) =>
      Promise.resolve({ data: { id: 7, slug: "mains", category_count: 0, ...payload } })
    );
    api.delete = vi.fn(() => Promise.resolve({ data: {} }));
  });

  const group = (overrides = {}) => ({
    name: "Mains",
    name_i18n: { fr: "Plats" },
    description: "Hearty mains, served all day",
    description_i18n: { fr: "Plats copieux" },
    image_url: "example.com/cover.jpg",
    position: 0,
    is_published: true,
    is_temporarily_disabled: false,
    disabled_note: "",
    ...overrides,
  });

  it("POSTs description, description_i18n and image_url when creating", async () => {
    await superCategoryApi.upsert(group());
    expect(api.post).toHaveBeenCalledTimes(1);
    const [, payload] = api.post.mock.calls[0];
    expect(payload.name).toBe("Mains");
    expect(payload.description).toBe("Hearty mains, served all day");
    expect(payload.description_i18n).toEqual({ fr: "Plats copieux" });
    expect(payload.image_url).toBe("https://example.com/cover.jpg");
  });

  it("PUTs description, description_i18n and image_url when updating", async () => {
    await superCategoryApi.upsert(group({ id: 7, slug: "mains" }));
    expect(api.put).toHaveBeenCalledTimes(1);
    expect(api.put.mock.calls[0][0]).toBe("/super-categories/7/");
    const [, payload] = api.put.mock.calls[0];
    expect(payload.description).toBe("Hearty mains, served all day");
    expect(payload.description_i18n).toEqual({ fr: "Plats copieux" });
    expect(payload.image_url).toBe("https://example.com/cover.jpg");
  });
});

// ── A3-05 — super-category delete: live counts, confirm, immediate ──────────
// Before the fix removeByLocalId spliced the row with no confirm and only
// queued the DELETE for saveAll, guarded only by the load-time category_count
// (stale the moment a category is added elsewhere) — while the backend
// cascade-deletes the group's categories AND their dishes.
describe("S1-H A3-05 — super-category delete confirms live counts, deletes now", () => {
  let wrapper;

  const groupRow = (overrides = {}) => ({
    id: 7,
    name: "Mains",
    name_i18n: {},
    slug: "mains",
    description: "",
    description_i18n: {},
    image_url: "",
    position: 0,
    is_published: true,
    is_temporarily_disabled: false,
    disabled_note: "",
    category_count: 0,
    ...overrides,
  });

  // The group loads with a STALE category_count of 0, but a category + dish
  // were added elsewhere since — the delete must count live, not trust the row.
  const stubApi = ({ deleteImpl } = {}) => {
    api.get = vi.fn((url) => {
      if (url.includes("/super-categories/")) return Promise.resolve({ data: [groupRow()] });
      if (url.includes("/categories/")) {
        return Promise.resolve({ data: [{ id: 11, name: "Soups", super_category: 7 }] });
      }
      if (url.includes("/dishes/")) {
        return Promise.resolve({ data: [{ id: 21, name: "Soup", category: 11 }] });
      }
      return Promise.resolve({ data: {} });
    });
    api.post = vi.fn((url, payload) =>
      Promise.resolve({ data: { id: 9, slug: "x", category_count: 0, ...payload } })
    );
    api.put = vi.fn((url, payload) =>
      Promise.resolve({ data: { id: 7, slug: "mains", category_count: 0, ...payload } })
    );
    api.delete = deleteImpl || vi.fn(() => Promise.resolve({ data: {} }));
  };

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    stubApi();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountGroups = () =>
    shallowMount(StepSuperCategories, {
      global: { stubs: { Teleport: { template: "<slot />" } } },
    });

  const loadGroups = async () => {
    wrapper = mountGroups();
    await flushPromises();
    await flushPromises();
    expect(wrapper.text()).toContain("Mains");
  };

  const clickDelete = async () => {
    const btn = wrapper.find('button[aria-label="common.remove"]');
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();
    await flushPromises();
    await flushPromises();
  };

  const clickSave = async () => {
    const saveBtn = wrapper.findAll("button").find((b) => b.text().trim() === "common.save");
    expect(saveBtn.exists()).toBe(true);
    await saveBtn.trigger("click");
    await flushPromises();
    await flushPromises();
  };

  it("fetches live category/dish counts and DELETEs immediately on confirm", async () => {
    await loadGroups();
    await clickDelete();
    // Live counts were read before the confirm — not the stale load-time 0.
    expect(api.get).toHaveBeenCalledWith("/categories/");
    expect(api.get).toHaveBeenCalledWith("/dishes/");
    // …and the DELETE fired immediately, not queued for Save.
    expect(api.delete).toHaveBeenCalledTimes(1);
    expect(api.delete).toHaveBeenCalledWith("/super-categories/7/");
    expect(wrapper.text()).not.toContain("Mains");
  });

  it("does not fire the delete again when the (now empty) list is saved", async () => {
    await loadGroups();
    await clickDelete();
    expect(api.delete).toHaveBeenCalledTimes(1);
    await clickSave();
    expect(api.delete).toHaveBeenCalledTimes(1);
    expect(api.put).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("keeps the row when the server refuses the delete (combo-protected 409)", async () => {
    stubApi({
      deleteImpl: vi.fn(() => {
        const err = new Error("Cannot delete — a combo still uses a dish");
        err.status = 409;
        return Promise.reject(err);
      }),
    });
    await loadGroups();
    await clickDelete();
    expect(api.delete).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("Mains");
    expect(useToastStore().message).toBe("stepSuperCategories.comboProtectedDelete");
  });

  it("persists an edited description + cover image through Save (A3-04, component level)", async () => {
    await loadGroups();
    // Open the REAL list row's editor (the panel header renders the row name).
    const editBtn = wrapper.find('button[aria-label="common.edit"]');
    expect(editBtn.exists()).toBe(true);
    await editBtn.trigger("click");
    await flushPromises();
    const descInput = wrapper.find('input[aria-label="stepSuperCategories.descriptionLabel"]');
    expect(descInput.exists()).toBe(true);
    await descInput.setValue("Hearty mains, served all day");
    const imageInput = wrapper.find('input[aria-label="stepSuperCategories.imageUrlLabel"]');
    expect(imageInput.exists()).toBe(true);
    await imageInput.setValue("https://example.com/cover.jpg");
    // Close the editor (its footer button reads common.close), then Save.
    const closeBtn = wrapper.findAll("button").find((b) => b.text().trim() === "common.close");
    expect(closeBtn.exists()).toBe(true);
    await closeBtn.trigger("click");
    await flushPromises();
    await clickSave();
    expect(api.put).toHaveBeenCalledTimes(1);
    expect(api.put.mock.calls[0][0]).toBe("/super-categories/7/");
    const payload = api.put.mock.calls[0][1];
    expect(payload.description).toBe("Hearty mains, served all day");
    expect(payload.image_url).toBe("https://example.com/cover.jpg");
  });
});

// ── A3-07 — "Save & exit" saves the active step first ───────────────────────
// Before the fix saveAndExit only wrote the step number to localStorage, so
// unsaved step edits were lost when the wizard unmounted. The Wizard now calls
// the active step's exposed saver through its step ref and stays put when the
// save reports failure. The live step is stubbed with a saver here so the exit
// path can be driven without a real step; router.push itself is the base
// file's un-spied mock, so the tests assert the observable side effects — the
// saver ran, and the step index was persisted only after a successful save
// (vs. not persisted at all when the save reports failure).
describe("S1-H A3-07 — saveAndExit saves the active step first", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountWizardWithStepSaver = (saveImpl) => {
    const saveAllSpy = vi.fn(saveImpl);
    wrapper = mount(Wizard, {
      global: {
        stubs: {
          KeepAlive: { template: "<slot />" },
          StepStart: { template: "<div />", methods: { saveAll: saveAllSpy } },
        },
      },
    });
    return saveAllSpy;
  };

  const mountUnpublished = async (saveImpl) => {
    const tenant = useTenantStore();
    tenant.$patch({ meta: { slug: "demo", profile: { is_menu_published: false } } });
    const spy = mountWizardWithStepSaver(saveImpl);
    await flushPromises();
    await flushPromises();
    return spy;
  };

  const clickSaveAndExit = async () => {
    const btn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("onboardingWizard.saveAndExit"));
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();
    await flushPromises();
  };

  it("calls the step's save before persisting the step index", async () => {
    const spy = await mountUnpublished(() => Promise.resolve(true));
    await clickSaveAndExit();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem("resto:onboarding-step:v2:demo")).toBe("1");
  });

  it("does not persist or leave when the step save reports failure", async () => {
    const spy = await mountUnpublished(() => Promise.resolve(false));
    await clickSaveAndExit();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem("resto:onboarding-step:v2:demo")).toBeNull();
  });
});

// ── A3-09 — publish gate requires the brand check ───────────────────────────
// Before the fix canPublish was menu-only (categories + dishes) while the
// readiness list showed brand "missing" in amber and the Publish button stayed
// enabled — a menu could go live with no tagline, no contact details, no logo.
// The gate now also requires hasBrand (the same definition the list shows).
describe("S1-H A3-09 — publish gate requires the brand check", () => {
  let wrapper;
  let profileData;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    // S1-F's tests above leave a mockResolvedValue on profileApi.get (clearAllMocks
    // does not remove implementations). Restore the delegating default so this
    // describe's api.get "/profile/" seed actually reaches StepPublish.
    profileApi.get.mockRestore();
    profileData = { is_menu_published: false, tagline: "", phone: "", whatsapp: "", is_open: true };
    api.get = vi.fn((url) => {
      if (url.includes("/profile/")) return Promise.resolve({ data: profileData });
      if (url.includes("/super-categories/")) return Promise.resolve({ data: [] });
      if (url.includes("/categories/")) return Promise.resolve({ data: [] });
      if (url.includes("/dishes/")) return Promise.resolve({ data: [] });
      return Promise.resolve({ data: {} });
    });
    api.post = vi.fn(() => Promise.resolve({ data: {} }));
    api.put = vi.fn(() => Promise.resolve({ data: {} }));
    api.delete = vi.fn(() => Promise.resolve({ data: {} }));
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountPublish = async () => {
    wrapper = shallowMount(StepPublish, {
      global: { stubs: { RouterLink: { template: "<slot />" } } },
    });
    await flushPromises();
    await flushPromises();
    await flushPromises();
  };

  const publishButton = () =>
    wrapper.findAll("button").find((b) => b.text().includes("stepPublish.publishMenu"));

  it("disables Publish and names the brand when the menu is ready but the brand is missing", async () => {
    await mountPublish();
    expect(wrapper.text()).toContain("stepPublish.publishBrandRequirement");
    expect(wrapper.text()).not.toContain("stepPublish.publishRequirement");
    const btn = publishButton();
    expect(btn.exists()).toBe(true);
    expect(btn.attributes("disabled")).not.toBeUndefined();
  });

  // A3-46 (G4b-K1, tested in StepPublish.mount.test.js) redefined brand as
  // tagline AND a contact channel — the S1-H version of this test set only a
  // tagline, which no longer counts as a brand. Same intent, fixture updated.
  it("enables Publish once a tagline AND a contact channel are set (same menu, brand present)", async () => {
    profileData = { ...profileData, tagline: "Great food, honest prices", phone: "0612345678" };
    await mountPublish();
    expect(wrapper.text()).not.toContain("stepPublish.publishBrandRequirement");
    const btn = publishButton();
    expect(btn.exists()).toBe(true);
    expect(btn.attributes("disabled")).toBeUndefined();
  });
});
// ── Run 8 G4b-K2 (A3-30, A3-34, A3-44) — appended 2026-11-15 ──────────────
// The base shell tests + S1-F/S1-H blocks above are untouched; everything below
// this line is new. 9 tests: A3-34 leave guards (4), A3-30 preset labels (2),
// A3-44 StepBrand / StepPublish mount smoke (2), + 1 StepTheme behaviour test
// counted in the A3-30 pair.
//
// Mock notes — every vi.mock below is hoisted by Vitest, so it applies
// file-wide, and each factory is a SUPERSET of (or disjoint from) the base
// factories, so the tests above keep passing:
// - ../../composables/useConfirmModal is RE-MOCKED with a shared spy that
//   resolves true by default (the base factory created a fresh fn per call,
//   which no earlier test observes). S1-H's A3-05 delete tests rely on the
//   confirm resolving true — the spy preserves that — while the A3-34 tests
//   below can assert confirm was/wasn't called and flip it to false.
// - vue-router is NOT re-mocked: the base onBeforeRouteLeave vi.fn() stands,
//   and the guard under test is read back from its mock.calls.
const confirmSpy = vi.hoisted(() => vi.fn(() => Promise.resolve(true)));
vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({ confirm: confirmSpy }),
}));

import { onBeforeRouteLeave } from "vue-router";

// ── A3-34 — leave guards only fire after a real edit ──────────────────────
// Before the fix beforeUnload warned whenever the tenant was unpublished (zero
// edits or not) and onBeforeRouteLeave confirmed on ANY route leave, including
// the in-wizard Preview (/menu) and Launch (/owner/launch) links. The wizard
// now tracks dirty state from input/change events in the step panel and
// exempts the in-wizard destinations.
describe("G4b-K2 A3-34 — leave guards only fire after a real edit", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const mountUnpublished = async () => {
    const tenant = useTenantStore();
    tenant.$patch({ meta: { slug: "demo", profile: { is_menu_published: false } } });
    wrapper = mountWizard();
    await flushPromises();
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
  };

  // The guard Wizard registered at setup — the last onBeforeRouteLeave call.
  const lastGuard = () => onBeforeRouteLeave.mock.calls.at(-1)[0];
  const markDirty = async () => {
    await wrapper.find(".ui-panel").trigger("input");
  };

  it("lets a clean wizard leave without prompting (no confirm call)", async () => {
    await mountUnpublished();
    const result = await lastGuard()({ name: "owner-home", path: "/owner/home" });
    expect(result).toBe(true);
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("prompts once the wizard is dirty, and honours a cancel", async () => {
    await mountUnpublished();
    await markDirty();
    const result = await lastGuard()({ name: "owner-home", path: "/owner/home" });
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(result).toBe(true);

    confirmSpy.mockResolvedValueOnce(false);
    const cancelled = await lastGuard()({ name: "owner-home", path: "/owner/home" });
    expect(cancelled).toBe(false);
  });

  it("exempts the in-wizard Preview (/menu) and Launch (/owner/launch) links even when dirty", async () => {
    await mountUnpublished();
    await markDirty();
    expect(await lastGuard()({ name: "owner-launch", path: "/owner/launch" })).toBe(true);
    expect(await lastGuard()({ path: "/menu" })).toBe(true);
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("beforeunload only fires when dirty", async () => {
    await mountUnpublished();
    // Clean: the event is not cancelled.
    expect(window.dispatchEvent(new Event("beforeunload", { cancelable: true }))).toBe(true);
    // Dirty: the handler prevents the unload.
    await markDirty();
    expect(window.dispatchEvent(new Event("beforeunload", { cancelable: true }))).toBe(false);
  });
});

// ── A3-30 — theme preset labels go through t() ─────────────────────────────
// Before the fix THEME_PRESETS carried plain English `label` strings rendered
// verbatim in every locale. They now carry `labelKey` and StepTheme renders
// t(preset.labelKey) (see StepTheme.vue.patch, applied by the coordinator after
// G4b-G). The t() mock echoes keys, so the translated keys — not raw English —
// must appear.
describe("G4b-K2 A3-30 — theme preset labels go through t()", () => {
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

  const mountTheme = async () => {
    profileApi.get.mockResolvedValue({
      primary_color: "#0F766E",
      secondary_color: "#F59E0B",
      logo_url: "",
      hero_url: "",
    });
    wrapper = mount(StepTheme, {
      props: { standalone: false },
      global: { stubs: { TemplatePickerModal: true } },
    });
    await flushPromises();
    await nextTick();
  };

  it("renders translated preset label keys, not raw English names", async () => {
    await mountTheme();
    for (const key of [
      "stepTheme.presets.amberTeal",
      "stepTheme.presets.charcoalRed",
      "stepTheme.presets.forestLime",
      "stepTheme.presets.oceanCoral",
    ]) {
      expect(wrapper.text()).toContain(key);
    }
    expect(wrapper.text()).not.toContain("Amber Teal");
    expect(wrapper.text()).not.toContain("Charcoal Red");
  });

  it("clicking a preset applies it and names it via the translated label", async () => {
    await mountTheme();
    const btn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("stepTheme.presets.amberTeal"));
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await nextTick();
    expect(btn.attributes("aria-pressed")).toBe("true");
    expect(wrapper.text()).toContain("stepTheme.presetSelected");
    expect(wrapper.text()).toContain("stepTheme.presets.amberTeal");
  });
});

// ── A3-44 — StepBrand / StepPublish mount smoke (K2 remainder) ─────────────
// StepBrand and StepTheme already have S1-F tests and StepPublish S1-H tests in
// this file; these two add the K2 mount-smoke pair so every step component the
// cluster touches has a named mount test in the K2 block too.
describe("G4b-K2 A3-44 — StepBrand / StepPublish mount smoke", () => {
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

  it("StepBrand mounts with a loaded profile without a setup() crash", async () => {
    profileApi.get.mockResolvedValue({
      tagline: "Our place",
      description: "",
      business_hours_schedule: {},
      language: "en",
    });
    wrapper = mount(StepBrand, { props: { standalone: false } });
    await flushPromises();
    await nextTick();
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("stepBrand.title");
  });

  it("StepPublish mounts and renders its readiness section", async () => {
    // S1-F's tests above leave a mockResolvedValue on profileApi.get; restore
    // the delegating default so this test's api.get "/profile/" seed reaches it.
    profileApi.get.mockRestore();
    api.get = vi.fn((url) => {
      if (url.includes("/profile/")) {
        return Promise.resolve({
          data: { is_menu_published: false, tagline: "Great food", phone: "", whatsapp: "", is_open: true },
        });
      }
      return Promise.resolve({ data: [] });
    });
    api.post = vi.fn(() => Promise.resolve({ data: {} }));
    api.put = vi.fn(() => Promise.resolve({ data: {} }));
    api.delete = vi.fn(() => Promise.resolve({ data: {} }));
    wrapper = shallowMount(StepPublish, {
      global: { stubs: { RouterLink: { template: "<slot />" } } },
    });
    await flushPromises();
    await flushPromises();
    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    expect(wrapper.text()).toContain("stepPublish.readinessSection");
  });
});
