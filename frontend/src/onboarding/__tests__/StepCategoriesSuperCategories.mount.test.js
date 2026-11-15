/**
 * Mount tests for onboarding/StepCategories.vue + StepSuperCategories.vue —
 * Rostoy Run 8, G4b cluster H (gaps A3-10 cats, A3-22…A3-27).
 *
 * WHY: every gap here is a silent-loss or invisible-error path in the wizard's
 * category/group steps — dangling aria-describedby targets, a dead removedIds
 * loop, translation-only names dropped on save, orphan rows with nowhere to
 * show their error, a zero-group dead end, tab navigation discarding unsaved
 * edits, and a "Done"/"Close" that only closes the modal. Each test drives
 * the real component through the UI the owner actually touches.
 *
 * Pattern-faithful to onboarding/__tests__/Wizard.mount.test.js (S1-H block)
 * and StepDishes.mount.test.js:
 *   - mount (real template: list rows, editor + quick-add modals)
 *   - real pinia (tenant store seeded via $patch; entitlements.max_languages: 2
 *     so the FR translation chips render) + real toast store
 *   - useI18n / useConfirmModal / useVocabulary / useFocusTrap / vue-router
 *     mocked; Teleport + AppIcon stubbed inline so modal content is in
 *     wrapper.text()
 *   - the REAL lib/onboardingApi runs against a mocked lib/api, so the exact
 *     upsert payloads (A3-23) are asserted, not a stubbed-upsert echo
 *   - FE lessons: setValue on inputs (awaits a tick) before clicking, never
 *     wrapper.vm.<ref> + immediate click on a :disabled-bound button; open
 *     the REAL list row (panel headers render the row name)
 *
 * Destination in repo: frontend/src/onboarding/__tests__/StepCategoriesSuperCategories.mount.test.js
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { nextTick } from "vue";

// StepCategories / StepSuperCategories destructure EXACTLY { t } from useI18n().
// The mocked `t` echoes its key verbatim (param-less) or as `key({...})`
// (with params), so the components' own template keys are assertable.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// Confirm modal: hoisted state so each test chooses the answer. `calls` records
// every confirm (title/body) so the dirty-guard tests can assert the guard
// fired — or did not fire on a clean step.
const confirmState = vi.hoisted(() => ({ value: true, calls: [] }));
vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({
    confirm: (opts) => {
      confirmState.calls.push(opts);
      return Promise.resolve(confirmState.value);
    },
  }),
}));

// StepCategories destructures { isShop, groupSingular, groupPlural, itemPlural }
// from useVocabulary(); groupSingular is read as `.value` in script
// (createFirstGroup) AND groupPlural is rendered in the template, so these
// MUST be real refs — plain { value } objects are not unwrapped in templates.
vi.mock("../../composables/useVocabulary", async () => {
  const { ref } = await import("vue");
  return {
    useVocabulary: () => ({
      isShop: ref(false),
      groupSingular: ref("Menu"),
      groupPlural: ref("Categories"),
      itemSingular: ref("dish"),
      itemPlural: ref("dishes"),
    }),
  };
});

// Focus trap is setup-only; a no-op keeps the modal open/close paths hermetic.
vi.mock("../../composables/useFocusTrap", () => ({
  useFocusTrap: vi.fn(),
}));

// Router: hoisted call logs. drillIn / goToDishes / goToSuperCategories push or
// replace to owner-menu-builder; the tests assert the navigation happened (or
// was blocked by the dirty guard) from these logs.
const routerState = vi.hoisted(() => ({ pushCalls: [], replaceCalls: [] }));
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({
    push: (to) => {
      routerState.pushCalls.push(to);
      return Promise.resolve(to);
    },
    replace: (to) => {
      routerState.replaceCalls.push(to);
      return Promise.resolve(to);
    },
  }),
  onBeforeRouteLeave: vi.fn(),
}));

// lib/api: the transport under the REAL lib/onboardingApi. Hoisted spies so
// tests can re-programme the server rows per case.
const apiGetMock = vi.hoisted(() => vi.fn());
const apiPostMock = vi.hoisted(() => vi.fn());
const apiPutMock = vi.hoisted(() => vi.fn());
const apiPatchMock = vi.hoisted(() => vi.fn());
const apiDeleteMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: apiGetMock,
    post: apiPostMock,
    put: apiPutMock,
    patch: apiPatchMock,
    delete: apiDeleteMock,
    defaults: { baseURL: "/api" },
  },
}));

// The real lib/onboardingApi's imports, mocked so mounting stays hermetic.
vi.mock("../../lib/slug", () => ({
  slugify: (v) =>
    String(v || "item").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "item",
}));
vi.mock("../../i18n/translate", () => ({ translate: (k, fallback) => fallback || k }));
vi.mock("../../lib/staleCache", () => ({ bustCache: vi.fn() }));

import StepCategories from "../StepCategories.vue";
import StepSuperCategories from "../StepSuperCategories.vue";
import { useTenantStore } from "../../stores/tenant";

const GROUP = (over = {}) => ({
  id: 7,
  name: "Menu",
  name_i18n: {},
  slug: "menu",
  position: 0,
  is_published: true,
  is_temporarily_disabled: false,
  disabled_note: "",
  category_count: 0,
  ...over,
});

const CAT = (over = {}) => ({
  id: 5,
  name: "Soups",
  name_i18n: {},
  slug: "soups",
  super_category: 7,
  super_category_slug: "menu",
  super_category_name: "Menu",
  description: "",
  description_i18n: {},
  image_url: "",
  position: 0,
  is_published: true,
  is_temporarily_disabled: false,
  course: 0,
  station: "",
  dish_count: 0,
  ...over,
});

let groupsData;
let catsData;
let dishesData;

const seedTenant = () => {
  const tenant = useTenantStore();
  tenant.$patch({
    meta: {
      slug: "demo",
      profile: { language: "en", is_menu_published: false },
      entitlements: { max_languages: 2 },
    },
  });
};

const mountCats = (props = {}) =>
  mount(StepCategories, {
    props: { standalone: false, ...props },
    global: {
      stubs: {
        Teleport: { template: "<slot />" },
        AppIcon: { template: "<span />" },
      },
    },
  });

const mountSupers = () =>
  mount(StepSuperCategories, {
    global: {
      stubs: {
        Teleport: { template: "<slot />" },
        AppIcon: { template: "<span />" },
      },
    },
  });

// Load the component (onMounted load() + the dirty-baseline watcher) before
// any assertion touches rows.
const settle = async () => {
  await flushPromises();
  await flushPromises();
  await nextTick();
};

const saveButton = (wrapper) =>
  wrapper.findAll("button").find((b) => b.text().trim() === "common.save");

const clickSave = async (wrapper) => {
  const btn = saveButton(wrapper);
  expect(btn.exists()).toBe(true);
  await btn.trigger("click");
  await settle();
};

const buttonsWith = (wrapper, text) =>
  wrapper.findAll("button").filter((b) => b.text().includes(text));

describe("StepCategories / StepSuperCategories — G4b-H (A3-10, A3-22…A3-27)", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    seedTenant();
    vi.clearAllMocks();
    confirmState.value = true;
    confirmState.calls = [];
    routerState.pushCalls = [];
    routerState.replaceCalls = [];
    groupsData = [GROUP()];
    catsData = [];
    dishesData = [];
    apiGetMock.mockImplementation((url) => {
      if (String(url).includes("/super-categories/")) return Promise.resolve({ data: groupsData });
      if (String(url).includes("/categories/")) return Promise.resolve({ data: catsData });
      if (String(url).includes("/dishes/")) return Promise.resolve({ data: dishesData });
      return Promise.resolve({ data: {} });
    });
    apiPostMock.mockImplementation((url, payload) =>
      Promise.resolve({
        data: { id: 99, slug: payload?.slug || "x", category_count: 0, ...(payload || {}) },
      })
    );
    apiPutMock.mockImplementation((url, payload) => {
      const m = String(url).match(/\/(\d+)\//);
      return Promise.resolve({
        data: { id: m ? Number(m[1]) : 99, slug: payload?.slug || "x", category_count: 0, ...(payload || {}) },
      });
    });
    apiPatchMock.mockResolvedValue({ data: {} });
    apiDeleteMock.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── A3-10 — dangling aria-describedby (StepCategories) ────────────────────
  it("A3-10 editor: the name input has no aria-describedby until its error exists, then points at it", async () => {
    catsData = [CAT()];
    wrapper = mountCats();
    await settle();

    // Open the REAL list row's editor (the panel header renders the row name).
    const editBtn = wrapper.find('button[aria-label="common.edit"]');
    expect(editBtn.exists()).toBe(true);
    await editBtn.trigger("click");
    await nextTick();

    const nameInput = wrapper.find('input[aria-label="stepCategories.categoryNamePlaceholder"]');
    expect(nameInput.exists()).toBe(true);
    expect(nameInput.attributes("aria-describedby")).toBeUndefined();

    // A 1-character name fails validateClient on Save.
    await nameInput.setValue("x");
    await clickSave(wrapper);
    expect(wrapper.text()).toContain("stepCategories.nameMin");
    const describedBy = wrapper
      .find('input[aria-label="stepCategories.categoryNamePlaceholder"]')
      .attributes("aria-describedby");
    expect(describedBy).toBe("step-cat-name-error-5");
  });

  it("A3-10 quick-add: super-category and name inputs gain aria-describedby only when their error is set", async () => {
    wrapper = mountCats();
    await settle();

    await buttonsWith(wrapper, "stepCategories.addCategory")[0].trigger("click");
    await nextTick();

    // NOTE: re-query the dialog controls before EVERY assertion/action. The
    // select node found right after opening the dialog is DETACHED by submit
    // time (the dialog subtree re-renders when the model/options settle), so a
    // held wrapper reads a stale node: its describedby stays undefined while
    // the LIVE select (verified via the error <p>'s label) correctly carries
    // aria-describedby + aria-invalid. The implementation is correct; the
    // original test held a stale node. Same for the name input.
    const quickSupcatSelect = () =>
      wrapper.findAll("select").filter((s) => s.element.closest('div[role="dialog"]'))[0];
    const quickNameInput = () =>
      wrapper.find('input[aria-label="stepCategories.categoryNamePlaceholder"]');
    expect(quickSupcatSelect().exists()).toBe(true);
    expect(quickNameInput().exists()).toBe(true);
    expect(quickSupcatSelect().attributes("aria-describedby")).toBeUndefined();
    expect(quickNameInput().attributes("aria-describedby")).toBeUndefined();

    // Empty the super-category, then submit: the super-category error appears.
    // NOTE: the select has no blank option by design (it always defaults to the
    // first group), so setValue("") cannot empty it — jsdom keeps the first
    // option selected and the model stays truthy. Empty the MODEL instead: that
    // is exactly the zero-groups state (openQuickModal falls back to "" when no
    // group exists), and quickAdd's own validation must set the error from it.
    wrapper.vm.quickCategory.super_category = "";
    await nextTick();
    await buttonsWith(wrapper, "stepCategories.addCategory").at(-1).trigger("click");
    await nextTick();
    expect(quickSupcatSelect().attributes("aria-describedby")).toBe("step-cat-quick-supcat-error");

    // Restore the group and submit again: now the name error appears.
    await quickSupcatSelect().setValue("7");
    await buttonsWith(wrapper, "stepCategories.addCategory").at(-1).trigger("click");
    await nextTick();
    expect(quickNameInput().attributes("aria-describedby")).toBe("step-cat-quick-name-error");
  });

  // ── A3-22 — removedIds is dead code ───────────────────────────────────────
  it("A3-22: deleting a saved category fires exactly one DELETE — Save does not re-delete it", async () => {
    catsData = [CAT()];
    wrapper = mountCats();
    await settle();

    const deleteBtn = wrapper.find('button[aria-label="common.remove"]');
    expect(deleteBtn.exists()).toBe(true);
    await deleteBtn.trigger("click");
    await settle();
    expect(apiDeleteMock).toHaveBeenCalledTimes(1);
    expect(apiDeleteMock).toHaveBeenCalledWith("/categories/5/");
    expect(wrapper.text()).not.toContain("Soups");

    await clickSave(wrapper);
    expect(apiDeleteMock).toHaveBeenCalledTimes(1);
  });

  // ── A3-23 — translation-only name is saved, not dropped ──────────────────
  it("A3-23: a category named only in French is saved under that name (not dropped)", async () => {
    catsData = [CAT({ name: "", name_i18n: { fr: "Soupes" }, slug: "" })];
    wrapper = mountCats();
    await settle();

    await clickSave(wrapper);
    expect(apiPutMock).toHaveBeenCalledTimes(1);
    expect(apiPutMock.mock.calls[0][0]).toBe("/categories/5/");
    const payload = apiPutMock.mock.calls[0][1];
    expect(payload.name).toBe("Soupes");
    expect(payload.name_i18n).toEqual({ fr: "Soupes" });
  });

  it("A3-23 quick-add: a name typed only under the FR tab creates the category", async () => {
    wrapper = mountCats();
    await settle();

    await buttonsWith(wrapper, "stepCategories.addCategory")[0].trigger("click");
    await nextTick();
    // Locale chips render [EN, FR] for the name field first; pick FR.
    const nameChips = wrapper.findAll("button[aria-pressed]");
    expect(nameChips.length).toBeGreaterThanOrEqual(2);
    await nameChips[1].trigger("click");
    await nextTick();
    await wrapper.find('input[aria-label="stepCategories.categoryNamePlaceholder"]').setValue("Soupes");
    await buttonsWith(wrapper, "stepCategories.addCategory").at(-1).trigger("click");
    await nextTick();

    expect(wrapper.text()).toContain("Soupes");
  });

  // ── A3-24 — orphan category gets a visible row + error ────────────────────
  it("A3-24: an orphan category renders in the Unassigned section with its row error", async () => {
    catsData = [CAT({ id: 6, name: "Orphan Soup", super_category: "", slug: "orphan-soup" })];
    wrapper = mountCats();
    await settle();

    expect(wrapper.text()).toContain("stepCategories.unassignedHeading");
    expect(wrapper.text()).toContain("Orphan Soup");
    await clickSave(wrapper);
    expect(wrapper.text()).toContain("stepCategories.superCategoryRequired");

    const editBtn = wrapper.find('button[aria-label="common.edit"]');
    expect(editBtn.exists()).toBe(true);
    await editBtn.trigger("click");
    await nextTick();
    expect(wrapper.text()).toContain("stepCategories.editCategory");
  });

  // ── A3-25 — no super-category management in the wizard ───────────────────
  it("A3-25: with zero groups the empty state links to menu-group management, and Create still seeds a first group", async () => {
    groupsData = [];
    wrapper = mountCats();
    await settle();

    expect(wrapper.text()).toContain("stepCategories.addSuperCategoriesFirst");
    const manageBtn = buttonsWith(wrapper, "stepCategories.manageSuperCategories")[0];
    expect(manageBtn.exists()).toBe(true);
    await manageBtn.trigger("click");
    await settle();
    expect(routerState.pushCalls).toEqual([
      { name: "owner-menu-builder", query: { tab: "super-categories" } },
    ]);

    const createBtn = buttonsWith(wrapper, "stepSuperCategories.add")[0];
    expect(createBtn.exists()).toBe(true);
    await createBtn.trigger("click");
    await settle();
    expect(apiPostMock).toHaveBeenCalledWith(
      "/super-categories/",
      expect.objectContaining({ name: "Menu" })
    );
  });

  // ── A3-26 — goToDishes dirty-check (StepCategories) ───────────────────────
  it("A3-26 StepCategories: navigating to dishes with unsaved edits asks first and stays put on 'no'", async () => {
    catsData = [CAT()];
    wrapper = mountCats({ standalone: true });
    await settle();

    await wrapper.find('button[aria-label="common.edit"]').trigger("click");
    await nextTick();
    await wrapper.find('input[aria-label="stepCategories.categoryNamePlaceholder"]').setValue("Soups!");
    await buttonsWith(wrapper, "common.close")[0].trigger("click");
    await nextTick();

    confirmState.value = false;
    await wrapper.find('div[role="button"]').trigger("click");
    await settle();
    expect(confirmState.calls.length).toBe(1);
    expect(confirmState.calls[0].title).toBe("stepCategories.unsavedChangesTitle");
    expect(routerState.replaceCalls).toEqual([]);

    confirmState.value = true;
    await wrapper.find('div[role="button"]').trigger("click");
    await settle();
    expect(routerState.replaceCalls).toEqual([
      { name: "owner-menu-builder", query: { tab: "dishes", category: "5" } },
    ]);
  });

  // ── A3-26 — drillIn dirty-check (StepSuperCategories) ─────────────────────
  it("A3-26 StepSuperCategories: drilling in clean navigates without asking; dirty asks and stays put on 'no'", async () => {
    groupsData = [GROUP()];
    wrapper = mountSupers();
    await settle();

    const drillBtn = () => wrapper.find('button[aria-label="stepSuperCategories.openCategories"]');
    expect(drillBtn().exists()).toBe(true);
    await drillBtn().trigger("click");
    await settle();
    expect(confirmState.calls).toEqual([]);
    expect(routerState.pushCalls).toEqual([
      { name: "owner-menu-builder", query: { tab: "categories", super: "7" } },
    ]);

    routerState.pushCalls = [];
    await wrapper.find('button[aria-label="common.edit"]').trigger("click");
    await nextTick();
    await wrapper.find('input[aria-label="stepSuperCategories.namePlaceholder"]').setValue("Mains!");
    await buttonsWith(wrapper, "common.close")[0].trigger("click");
    await nextTick();

    confirmState.value = false;
    await drillBtn().trigger("click");
    await settle();
    expect(confirmState.calls.length).toBe(1);
    expect(confirmState.calls[0].title).toBe("stepSuperCategories.unsavedChangesTitle");
    expect(routerState.pushCalls).toEqual([]);

    confirmState.value = true;
    await drillBtn().trigger("click");
    await settle();
    expect(routerState.pushCalls).toEqual([
      { name: "owner-menu-builder", query: { tab: "categories", super: "7" } },
    ]);
  });

  // ── A3-27 — dirty indicator on the editor + row ───────────────────────────
  it("A3-27: an edited group shows an Unsaved badge and a 'Done - not saved yet' footer; Save clears the badge", async () => {
    groupsData = [GROUP()];
    wrapper = mountSupers();
    await settle();

    expect(wrapper.text()).not.toContain("stepSuperCategories.unsavedBadge");
    await wrapper.find('button[aria-label="common.edit"]').trigger("click");
    await nextTick();
    await wrapper.find('input[aria-label="stepSuperCategories.namePlaceholder"]').setValue("Mains!");

    expect(wrapper.text()).toContain("stepSuperCategories.unsavedBadge");
    expect(wrapper.text()).toContain("stepSuperCategories.unsavedHint");
    expect(wrapper.text()).toContain("stepSuperCategories.doneUnsaved");

    await clickSave(wrapper);
    expect(apiPutMock).toHaveBeenCalledWith("/super-categories/7/", expect.objectContaining({ name: "Mains!" }));
    expect(wrapper.text()).not.toContain("stepSuperCategories.unsavedBadge");
    expect(wrapper.text()).not.toContain("stepSuperCategories.doneUnsaved");
  });

  it("A3-27 + A3-10 (super-categories): a clean editor still says Close, with no dangling aria-describedby", async () => {
    groupsData = [GROUP()];
    wrapper = mountSupers();
    await settle();

    await wrapper.find('button[aria-label="common.edit"]').trigger("click");
    await nextTick();
    expect(wrapper.text()).not.toContain("stepSuperCategories.doneUnsaved");
    expect(wrapper.text()).not.toContain("stepSuperCategories.unsavedHint");
    expect(wrapper.text()).toContain("common.close");
    const nameInput = wrapper.find('input[aria-label="stepSuperCategories.namePlaceholder"]');
    expect(nameInput.exists()).toBe(true);
    expect(nameInput.attributes("aria-describedby")).toBeUndefined();
  });
});
