/**
 * Mount tests for onboarding/StepDishes.vue — Rostoy Run 8, Surface 1, cluster
 * S1-G (gaps A3-02, A3-03, A3-06).
 *
 * WHY: these three P1s are all silent-failure paths in the dishes step — a
 * quick-added dish's image deleted before save, "mark unavailable" never
 * reaching the server, and bulk-price / CSV-import reloads wiping unsaved
 * edits. Each test drives the real component (mount, not shallow) through the
 * UI the owner actually touches, with lib/onboardingApi + lib/api mocked.
 *
 * Pattern-faithful to onboarding/__tests__/Wizard.mount.test.js and
 * pages/__tests__/OwnerMenuBuilder.mount.test.js:
 *   - mount (real template: list rows, quick-add / bulk-price / CSV modals)
 *   - real pinia (tenant store seeded via $patch so defaultLocale /
 *     availableContentLocales resolve; toast store runs for real)
 *   - useI18n / useConfirmModal / useVocabulary / useTranslate / useFocusTrap /
 *     vue-router mocked; Teleport + AppIcon stubbed inline so modal content is
 *     in wrapper.text()
 *   - FE lessons: setValue on inputs (awaits a tick) before clicking, never
 *     wrapper.vm.<ref> + immediate click on a :disabled-bound button
 *
 * Destination in repo: frontend/src/onboarding/__tests__/StepDishes.mount.test.js
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";
import { nextTick } from "vue";

// StepDishes destructures EXACTLY { t } from useI18n(). The mocked `t` echoes
// its key verbatim (param-less) or as `key({...})` (with params).
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// StepDishes destructures { confirm } from useConfirmModal() (bulk actions,
// remove). Resolve true so the confirmed path runs in every test.
vi.mock("../../composables/useConfirmModal", () => ({
  useConfirmModal: () => ({ confirm: vi.fn(() => Promise.resolve(true)) }),
}));

// StepDishes destructures { isShop, itemSingular, itemPlural, groupPlural }
// from useVocabulary(); all four are template-only (no .value read in script),
// mocked as ref-like { value } exactly like the real composable returns.
vi.mock("../../composables/useVocabulary", () => ({
  useVocabulary: () => ({
    isShop: { value: false },
    itemSingular: { value: "dish" },
    itemPlural: { value: "dishes" },
    groupPlural: { value: "categories" },
  }),
}));

// useTranslate is only used for the per-field translate buttons (never at
// mount). translating is indexed in the template, translateError is read as
// .value in script — both shapes are mocked faithfully.
vi.mock("../../composables/useTranslate", () => ({
  useTranslate: () => ({
    translating: {},
    translateError: { value: "" },
    translateField: vi.fn(() => Promise.resolve(null)),
  }),
}));

// Focus trap is setup-only (three useFocusTrap calls); a no-op keeps the
// modal open/close paths hermetic.
vi.mock("../../composables/useFocusTrap", () => ({
  useFocusTrap: vi.fn(),
}));

// StepDishes imports { useRoute } from vue-router; syncActiveCategory reads
// route.query.category at setup (empty here).
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

// lib/api: used for the bulk-price PATCH, the CSV-import POST and the template
// GET. Hoisted spies so tests can re-programme per case.
const apiGetMock = vi.hoisted(() => vi.fn());
const apiPostMock = vi.hoisted(() => vi.fn());
const apiPatchMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({
  // shared canonical extractor (added to lib/api; mock returns the fallback)
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: apiGetMock,
    post: apiPostMock,
    put: vi.fn(() => Promise.resolve({ data: {} })),
    patch: apiPatchMock,
    delete: vi.fn(() => Promise.resolve({ data: {} })),
    defaults: { baseURL: "/api" },
  },
}));

// lib/onboardingApi: the whole dish/category surface, hoisted spies.
const categoryListMock = vi.hoisted(() => vi.fn());
const dishListMock = vi.hoisted(() => vi.fn());
const dishUpsertMock = vi.hoisted(() => vi.fn());
const dishRemoveMock = vi.hoisted(() => vi.fn());
const optionSyncMock = vi.hoisted(() => vi.fn());
const groupSyncMock = vi.hoisted(() => vi.fn());
const uploadRemoveMock = vi.hoisted(() => vi.fn());
const uploadImageMock = vi.hoisted(() => vi.fn());
vi.mock("../../lib/onboardingApi", () => ({
  categoryApi: { list: categoryListMock },
  dishApi: { list: dishListMock, upsert: dishUpsertMock, remove: dishRemoveMock },
  dishOptionApi: { syncForDish: optionSyncMock },
  optionGroupApi: { syncForDish: groupSyncMock },
  uploadApi: { removeImage: uploadRemoveMock, image: uploadImageMock },
}));

import StepDishes from "../StepDishes.vue";
import { useTenantStore } from "../../stores/tenant";

const CATEGORIES = [{ id: 1, name: "Mains", super_category_name: "", position: 0 }];

const serverDish = (over = {}) => ({
  id: 7,
  name: "Soup",
  category: 1,
  price: 10,
  currency: "MAD",
  image_url: "",
  stock_qty: 5,
  is_available: true,
  is_published: true,
  position: 0,
  ...over,
});

const seedTenant = () => {
  const tenant = useTenantStore();
  tenant.$patch({
    meta: {
      slug: "demo",
      profile: { language: "en", is_menu_published: false },
      plan: { max_languages: 1 },
    },
  });
};

const mountDishes = () =>
  mount(StepDishes, {
    global: {
      stubs: {
        Teleport: { template: "<slot />" },
        AppIcon: { template: "<span />" },
      },
    },
  });

// Buttons are found by their echoed i18n key (mocked t renders the key).
const buttonsWith = (wrapper, text) =>
  wrapper.findAll("button").filter((b) => b.text().includes(text));

const openQuickAdd = async (wrapper) => {
  await buttonsWith(wrapper, "stepDishes.addDishToCategory")[0].trigger("click");
  await nextTick();
};

const fillQuickDishName = async (wrapper, name) => {
  await wrapper
    .find('input[aria-label^="stepDishes.dishNamePlaceholder"]')
    .setValue(name);
};

const submitQuickAdd = async (wrapper) => {
  await buttonsWith(wrapper, "stepDishes.addDishToCategory").at(-1).trigger("click");
  await flushPromises();
  await flushPromises();
};

describe("StepDishes (owner onboarding) — S1-G: A3-02 / A3-03 / A3-06", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    categoryListMock.mockResolvedValue([...CATEGORIES]);
    dishListMock.mockResolvedValue([]);
    dishUpsertMock.mockImplementation(async (dish) => ({
      id: dish.id || 99,
      slug: dish.slug || "dish",
      stock_qty: dish.stock_qty ?? null,
      is_available: dish.is_available ?? true,
    }));
    optionSyncMock.mockResolvedValue([]);
    groupSyncMock.mockResolvedValue([]);
    uploadRemoveMock.mockResolvedValue(undefined);
    apiPatchMock.mockResolvedValue({ data: {} });
    apiPostMock.mockResolvedValue({ data: {} });
    apiGetMock.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── A3-02: quick-added dish keeps its uploaded image ──────────────────────
  // Regression: quickAddDish() built the row WITH image_url, then called
  // closeQuickDishModal() — which deleted the managed upload — and only
  // afterwards persistDish(row). The dish was saved pointing at a deleted file.
  it("A3-02: quick-add keeps the uploaded image (no delete before persist)", async () => {
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    await openQuickAdd(wrapper);
    await fillQuickDishName(wrapper, "Tomato Soup");
    wrapper.vm.quickDish.image_url = "/uploads/tomato-soup.jpg";
    await nextTick();
    await submitQuickAdd(wrapper);

    expect(uploadRemoveMock).not.toHaveBeenCalledWith("/uploads/tomato-soup.jpg");
    expect(dishUpsertMock).toHaveBeenCalled();
    expect(dishUpsertMock.mock.calls[0][0].image_url).toBe("/uploads/tomato-soup.jpg");
    expect(wrapper.text()).toContain("Tomato Soup");
  });

  // The discard path must be unchanged: closing the modal without adding
  // still deletes the managed upload.
  it("A3-02: closing the quick-add modal without adding still deletes the managed upload", async () => {
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    await openQuickAdd(wrapper);
    wrapper.vm.quickDish.image_url = "/uploads/tomato-soup.jpg";
    await nextTick();
    await buttonsWith(wrapper, "common.close")[0].trigger("click");
    await flushPromises();

    expect(uploadRemoveMock).toHaveBeenCalledWith("/uploads/tomato-soup.jpg");
  });

  // ── A3-03: availability reaches the server and survives reload ────────────
  // Regression: normalize() dropped is_available on load (sold-out badge could
  // never reflect server state) and dishApi.upsert only sent it in the restock
  // branch, so bulk mark-available/unavailable was local-only — and
  // rememberSaved() then snapshotted the local value as "saved", so a later
  // save skipped the row entirely.
  it("A3-03: a dish stored unavailable keeps its sold-out badge after reload", async () => {
    dishListMock.mockResolvedValue([serverDish({ is_available: false })]);
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    expect(wrapper.text()).toContain("Soup");
    expect(wrapper.text()).toContain("stepDishes.outOfStock");
  });

  it("A3-03: bulk mark-unavailable reaches the server on save", async () => {
    dishListMock.mockResolvedValue([serverDish({ is_available: true })]);
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    expect(wrapper.text()).not.toContain("stepDishes.outOfStock");
    await buttonsWith(wrapper, "stepDishes.bulkMarkUnavailable")[0].trigger("click");
    await flushPromises();
    // Local badge flips immediately…
    expect(wrapper.text()).toContain("stepDishes.outOfStock");

    // …and the page Save persists it (the row is dirty, so saveAndNext sends it).
    await buttonsWith(wrapper, "common.saveAndNext")[0].trigger("click");
    await flushPromises();
    await flushPromises();

    expect(dishUpsertMock).toHaveBeenCalled();
    expect(dishUpsertMock.mock.calls[0][0].is_available).toBe(false);
  });

  // ── A3-06: bulk-price / CSV-import reloads keep unsaved edits ─────────────
  // Regression: applyBulkPrice and submitCsvImport both called load() on
  // success, and load() spliced the whole list from the server — any unsaved
  // dish edits (including a just-quick-added dish whose persist failed)
  // vanished silently.
  it("A3-06: bulk-price apply keeps a quick-added dish whose persist failed", async () => {
    dishListMock.mockResolvedValue([serverDish({ price: 10 })]);
    dishUpsertMock.mockRejectedValueOnce(new Error("save failed"));
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    // Quick-add a dish; its immediate persist fails, so it stays local + dirty.
    await openQuickAdd(wrapper);
    await fillQuickDishName(wrapper, "New Dish");
    await submitQuickAdd(wrapper);
    expect(wrapper.text()).toContain("New Dish");
    expect(dishUpsertMock).toHaveBeenCalledTimes(1);

    // The server now has the repriced dish; bulk-price apply reloads the list.
    dishListMock.mockResolvedValue([serverDish({ price: 11 })]);
    apiPatchMock.mockImplementation(async (url, payload) =>
      payload?.dry_run
        ? { data: { items: [{ id: 7, name: "Soup", price_before: 10, price_after: 11 }] } }
        : { data: { updated: 1 } }
    );
    await buttonsWith(wrapper, "stepDishes.bulkPriceAdjust")[0].trigger("click");
    await nextTick();
    await wrapper.find('input[aria-label="stepDishes.bulkPriceValue"]').setValue("10");
    await buttonsWith(wrapper, "stepDishes.bulkPricePreviewBtn")[0].trigger("click");
    await flushPromises();
    await flushPromises();
    await buttonsWith(wrapper, "stepDishes.bulkPriceApplyBtn")[0].trigger("click");
    await flushPromises();
    await flushPromises();

    // The dirty local row survived the reload; the clean row took the server price.
    expect(wrapper.text()).toContain("New Dish");
    expect(wrapper.text()).toContain("11.00");
  });

  it("A3-06: CSV-import success keeps a quick-added dish whose persist failed", async () => {
    dishListMock.mockResolvedValue([serverDish({ price: 10 })]);
    dishUpsertMock.mockRejectedValueOnce(new Error("save failed"));
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    await openQuickAdd(wrapper);
    await fillQuickDishName(wrapper, "New Dish");
    await submitQuickAdd(wrapper);
    expect(wrapper.text()).toContain("New Dish");

    // The server gained an imported dish; import success reloads the list.
    dishListMock.mockResolvedValue([
      serverDish({ price: 10 }),
      serverDish({ id: 8, name: "Salad", price: 7 }),
    ]);
    apiPostMock.mockResolvedValue({ data: { created_dishes: 1 } });
    await buttonsWith(wrapper, "stepDishes.csvImportBtn")[0].trigger("click");
    await nextTick();
    const fileInput = wrapper.find("#csv-import-file-input");
    const file = new File(["name,price\nSalad,7"], "menu.csv", { type: "text/csv" });
    Object.defineProperty(fileInput.element, "files", { value: [file] });
    await fileInput.trigger("change");
    await buttonsWith(wrapper, "stepDishes.csvImportSubmit")[0].trigger("click");
    await flushPromises();
    await flushPromises();

    expect(wrapper.text()).toContain("New Dish");
    expect(wrapper.text()).toContain("Salad");
  });
});

describe("StepDishes (owner onboarding) - G4b-I: A3-13 / A3-14 / A3-15 / A3-16 / A3-17 / A3-21 / A3-42", () => {
  let wrapper;

  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    categoryListMock.mockResolvedValue([...CATEGORIES]);
    dishListMock.mockResolvedValue([]);
    dishUpsertMock.mockImplementation(async (dish) => ({
      id: dish.id || 99,
      slug: dish.slug || "dish",
      stock_qty: dish.stock_qty ?? null,
      is_available: dish.is_available ?? true,
    }));
    optionSyncMock.mockResolvedValue([]);
    groupSyncMock.mockResolvedValue([]);
    uploadRemoveMock.mockResolvedValue(undefined);
    apiPatchMock.mockResolvedValue({ data: {} });
    apiPostMock.mockResolvedValue({ data: {} });
    apiGetMock.mockResolvedValue({ data: {} });
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // The pencil button opens the editor; its aria-label is exactly the echoed
  // common.edit key (the row-name button carries "common.edit <name>").
  const openEditor = async (w, idx = 0) => {
    await w.findAll('button[aria-label="common.edit"]')[idx].trigger("click");
    await nextTick();
  };

  // Editor footer Save: text is exactly "common.save" — but the PAGE top bar
  // (line 10) ALSO reads "common.save" (only the bottom bar reads
  // "common.saveAndNext"), so an exact text match finds 2 buttons once the
  // editor is open. Scope to the editor dialog (role="dialog"); the page bar
  // is outside any dialog.
  const clickEditorSave = async (w) => {
    const saveBtn = w
      .findAll("button")
      .filter((b) => b.text().trim() === "common.save" && b.element.closest('div[role="dialog"]'));
    expect(saveBtn.length).toBe(1);
    await saveBtn[0].trigger("click");
    await flushPromises();
    await flushPromises();
  };

  const mountWithDishes = async (rows) => {
    dishListMock.mockResolvedValue(rows);
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();
    return wrapper;
  };

  const group = (over = {}) => ({
    name: "Size",
    name_i18n: {},
    min_select: 0,
    max_select: 1,
    position: 0,
    options: [{ name: "Small", name_i18n: {}, price_delta: 0, position: 0 }],
    ...over,
  });

  const dishWithGroups = (groups) =>
    serverDish({ option_groups: groups });

  // -- A3-13: option groups are validated client-side --
  it("A3-13: editor Save blocks a group with options but no name", async () => {
    await mountWithDishes([
      dishWithGroups([group({ name: "", options: [{ name: "Large", name_i18n: {}, price_delta: 0, position: 0 }] })]),
    ]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepDishes.groupNameRequired");
  });

  it("A3-13: editor Save blocks max_select below min_select", async () => {
    await mountWithDishes([
      dishWithGroups([group({ name: "Size", min_select: 2, max_select: 1 })]),
    ]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepDishes.groupMaxLessThanMin");
  });

  it("A3-13: editor Save blocks duplicate group names", async () => {
    await mountWithDishes([
      dishWithGroups([group({ name: "Size" }), group({ name: "size", position: 1 })]),
    ]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepDishes.groupNameDuplicate");
  });

  it("A3-13: editor Save blocks a negative group-option price", async () => {
    await mountWithDishes([
      dishWithGroups([
        group({
          name: "Extras",
          options: [{ name: "Cheese", name_i18n: {}, price_delta: -2, position: 0 }],
        }),
      ]),
    ]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepDishes.extraPriceMin");
  });

  it("A3-13: a valid option group saves through the editor", async () => {
    await mountWithDishes([
      dishWithGroups([
        group({
          name: "Size",
          min_select: 0,
          max_select: 2,
          options: [
            { name: "Small", name_i18n: {}, price_delta: 0, position: 0 },
            { name: "Large", name_i18n: {}, price_delta: 1.5, position: 1 },
          ],
        }),
      ]),
    ]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).toHaveBeenCalled();
  });

  it("A3-13: page Save blocks a dish with an invalid option group", async () => {
    await mountWithDishes([
      dishWithGroups([group({ name: "", options: [{ name: "Large", name_i18n: {}, price_delta: 0, position: 0 }] })]),
    ]);
    await buttonsWith(wrapper, "common.saveAndNext")[0].trigger("click");
    await flushPromises();
    await flushPromises();

    expect(dishUpsertMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepDishes.groupNameRequired");
  });

  // -- A3-14: availability schedule is validated client-side --
  it("A3-14: editor Save blocks a schedule with only a start time", async () => {
    await mountWithDishes([
      serverDish({ availability_schedule: { days: ["mon"], time_start: "09:00", time_end: "" } }),
    ]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepDishes.availabilityTimeBothOrNeither");
  });

  it("A3-14: editor Save blocks non-HH:MM schedule times", async () => {
    await mountWithDishes([
      serverDish({ availability_schedule: { days: [], time_start: "25:00", time_end: "26:00" } }),
    ]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepDishes.availabilityTimeInvalid");
  });

  it("A3-14: a valid schedule saves through the editor", async () => {
    await mountWithDishes([
      serverDish({ availability_schedule: { days: ["mon", "tue"], time_start: "09:00", time_end: "17:00" } }),
    ]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).toHaveBeenCalled();
  });

  // -- A3-15: inline price edit shows the error instead of silently reverting --
  it("A3-15: a negative inline price keeps the old price and shows priceMin", async () => {
    await mountWithDishes([serverDish({ price: 10 })]);

    await wrapper.find('span[aria-label="stepDishes.tapToEditPrice"]').trigger("click");
    await nextTick();
    const input = wrapper.find('input[aria-label="stepDishes.pricePlaceholder"]');
    await input.setValue(-5);
    await input.trigger("blur");
    await nextTick();

    expect(wrapper.text()).toContain("stepDishes.priceMin");
    expect(wrapper.text()).toContain("10.00");
    expect(wrapper.vm.dishes[0].price).toBe(10);
  });

  it("A3-15: a valid inline price commits and clears the error", async () => {
    await mountWithDishes([serverDish({ price: 10 })]);

    await wrapper.find('span[aria-label="stepDishes.tapToEditPrice"]').trigger("click");
    await nextTick();
    const input = wrapper.find('input[aria-label="stepDishes.pricePlaceholder"]');
    await input.setValue(12.5);
    await input.trigger("blur");
    await nextTick();

    expect(wrapper.text()).not.toContain("stepDishes.priceMin");
    expect(wrapper.text()).toContain("12.50");
    expect(wrapper.vm.dishes[0].price).toBe(12.5);
  });

  // -- A3-16: move up/down buttons reorder without dragging --
  it("A3-16: move-down swaps the two dishes; move-up is disabled on the first row", async () => {
    await mountWithDishes([
      serverDish({ id: 7, name: "Soup", price: 10, position: 0 }),
      serverDish({ id: 8, name: "Salad", price: 7, position: 1 }),
    ]);

    const moveUp = wrapper.findAll('button[aria-label="common.moveUp"]');
    const moveDown = wrapper.findAll('button[aria-label="common.moveDown"]');
    expect(moveUp.length).toBe(2);
    expect(moveUp[0].element.disabled).toBe(true);
    expect(moveDown[0].element.disabled).toBe(false);

    await moveDown[0].trigger("click");
    await nextTick();

    expect(wrapper.findAll("h3")[0].text()).toBe("Salad");
    expect(wrapper.findAll("h3")[1].text()).toBe("Soup");
    expect(wrapper.vm.dishes.find((d) => d.id === 8).position).toBe(0);
    expect(wrapper.vm.dishes.find((d) => d.id === 7).position).toBe(1);
  });

  // -- A3-17: clone drops translations + stock and is born available --
  it("A3-17: cloning a sold-out dish clears description_i18n, resets stock, sets available", async () => {
    await mountWithDishes([
      serverDish({
        id: 7,
        name: "Soup",
        description: "Tomato soup",
        description_i18n: { fr: "Soupe de tomate" },
        stock_qty: 3,
        is_available: false,
      }),
    ]);

    const cloneBtn = wrapper
      .findAll("button")
      .filter((b) => (b.attributes("aria-label") || "").startsWith("stepDishes.cloneDish"));
    expect(cloneBtn.length).toBe(1);
    await cloneBtn[0].trigger("click");
    await flushPromises();
    await nextTick();

    expect(wrapper.vm.dishes.length).toBe(2);
    const original = wrapper.vm.dishes.find((d) => d.id === 7);
    const clone = wrapper.vm.dishes.find((d) => d.id === undefined);
    expect(clone).toBeTruthy();
    expect(clone.description_i18n).toEqual({});
    expect(clone.stock_qty).toBeNull();
    expect(clone.is_available).toBe(true);
    expect(clone.name).toContain("stepDishes.cloneDishName");
    // The original is untouched.
    expect(original.stock_qty).toBe(3);
    expect(original.is_available).toBe(false);
    expect(original.description_i18n).toEqual({ fr: "Soupe de tomate" });
  });

  // -- A3-21: editor Save runs the full validation, not just name + category --
  it("A3-21: editor Save blocks a negative dish price", async () => {
    await mountWithDishes([serverDish({ price: -5 })]);
    await openEditor(wrapper);
    await clickEditorSave(wrapper);

    expect(dishUpsertMock).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("stepDishes.priceMin");
  });

  // -- A3-42: RTL availability-toggle knob --
  it("A3-42: the publish toggle reverses its knob slide in RTL", async () => {
    await mountWithDishes([serverDish({})]);
    expect(wrapper.html()).toContain("rtl:peer-checked:after:-translate-x-4");
  });
});
