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

// ── G4b-J: A3-10 / A3-18 / A3-19 / A3-20 / A3-38 / A3-39 ────────────────────
// Appended by cluster G4b-J (Rostoy Run 8). Base file above is untouched; these
// tests target the J patches (applied after cluster I's commit) and are run by
// the coordinator after staging. Same harness + mocks as the S1-G block above.
describe("StepDishes (owner onboarding) — G4b-J: A3-10 / A3-18 / A3-19 / A3-20 / A3-38 / A3-39", () => {
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

  const exactButton = (w, text) =>
    w.findAll("button").filter((b) => b.text().trim() === text);

  const openEditorFor = async (w, name) => {
    await w.find(`button[aria-label="common.edit ${name}"]`).trigger("click");
    await nextTick();
  };

  const setCsvFile = async (w) => {
    const fileInput = w.find("#csv-import-file-input");
    const file = new File(["name,price\nSalad,7"], "menu.csv", { type: "text/csv" });
    Object.defineProperty(fileInput.element, "files", { value: [file] });
    await fileInput.trigger("change");
  };

  // ── A3-10: aria-describedby is conditional on the error ────────────────
  it("A3-10: editor name input has no aria-describedby until its error appears", async () => {
    dishListMock.mockResolvedValue([serverDish()]);
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    await openEditorFor(wrapper, "Soup");
    const nameInput = () =>
      wrapper.find('input[aria-label^="stepDishes.dishNamePlaceholder"]');
    expect(nameInput().attributes("aria-describedby")).toBeUndefined();

    // A too-short name trips the row error on editor Save.
    await nameInput().setValue("x");
    await exactButton(wrapper, "common.save")[0].trigger("click");
    await nextTick();
    expect(nameInput().attributes("aria-describedby")).toContain(
      "step-dishes-name-error-"
    );
  });

  it("A3-10: quick-add name input and category select have no aria-describedby without an error", async () => {
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    await openQuickAdd(wrapper);
    const nameInput = wrapper.find(
      'input[aria-label^="stepDishes.dishNamePlaceholder"]'
    );
    expect(nameInput.attributes("aria-describedby")).toBeUndefined();
    // The top category picker has no describedby either; the quick-modal
    // select must not point at its (absent) error element.
    for (const select of wrapper.findAll(
      'select[aria-label="stepDishes.selectCategory"]'
    )) {
      expect(select.attributes("aria-describedby")).toBeUndefined();
    }
  });

  // ── A3-18: unsaved dishes can be combo components ──────────────────────
  // Regression: availableComboComponents required d.id, so a dish created in
  // this session but not yet saved could never be picked; the picker for a
  // fresh combo never even opened (its v-if needed length > 0).
  it("A3-18: an unsaved dish is offered as a combo component and saved first", async () => {
    dishListMock.mockResolvedValue([serverDish()]);
    dishUpsertMock.mockRejectedValueOnce(new Error("save failed"));
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    // Quick-add a dish whose immediate persist fails — it stays local + unsaved.
    await openQuickAdd(wrapper);
    await fillQuickDishName(wrapper, "Local Soup");
    await submitQuickAdd(wrapper);
    expect(wrapper.text()).toContain("Local Soup");
    expect(dishUpsertMock).toHaveBeenCalledTimes(1);

    // Open the saved dish's editor and switch combo mode on.
    await openEditorFor(wrapper, "Soup");
    const comboLabel = wrapper
      .findAll("label")
      .filter((l) => l.text().includes("combos.badge"))[0];
    await comboLabel.find("input").setChecked(true);
    await nextTick();

    // The picker now lists the unsaved dish, with the unsaved note shown.
    const picker = wrapper.find('select[aria-label="combos.addComponent"]');
    expect(picker.exists()).toBe(true);
    expect(picker.findAll("option").map((o) => o.text())).toContain("Local Soup");
    expect(wrapper.text()).toContain("stepDishes.comboUnsavedNote");

    const localOption = picker
      .findAll("option")
      .find((o) => o.text() === "Local Soup");
    await picker.setValue(localOption.attributes("value"));
    await buttonsWith(wrapper, "combos.addComponent")[0].trigger("click");
    await nextTick();

    // Saving the combo persists the component first, then the combo with the
    // resolved backend id.
    await exactButton(wrapper, "common.save")[0].trigger("click");
    await flushPromises();
    await flushPromises();
    await flushPromises();

    const calls = dishUpsertMock.mock.calls;
    expect(calls[1][0].name).toBe("Local Soup");
    expect(calls[2][0].name).toBe("Soup");
    expect(calls[2][0].combo_components[0].component_id).toBe(99);
  });

  // ── A3-19: bulk price scope note + translated error ─────────────────────
  it("A3-19: bulk-price modal discloses published-only scope and never shows raw backend detail", async () => {
    dishListMock.mockResolvedValue([serverDish()]);
    apiPatchMock.mockRejectedValue({
      response: { data: { detail: "Something exploded on the server" } },
    });
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    await buttonsWith(wrapper, "stepDishes.bulkPriceAdjust")[0].trigger("click");
    await nextTick();
    expect(wrapper.text()).toContain("stepDishes.bulkPricePublishedOnly");

    await wrapper
      .find('input[aria-label="stepDishes.bulkPriceValue"]')
      .setValue("10");
    await buttonsWith(wrapper, "stepDishes.bulkPricePreviewBtn")[0].trigger("click");
    await flushPromises();
    await flushPromises();

    // The shared extractor falls back to the translated generic error.
    expect(wrapper.text()).toContain("stepDishes.bulkPriceError");
    expect(wrapper.text()).not.toContain("Something exploded on the server");
  });

  // ── A3-20: CSV import shows skipped + per-row errors ───────────────────
  it("A3-20: a partial CSV import shows skipped rows and per-row errors", async () => {
    dishListMock.mockResolvedValue([
      serverDish(),
      serverDish({ id: 8, name: "Salad", price: 7 }),
    ]);
    apiPostMock.mockResolvedValue({
      data: {
        created_dishes: 1,
        created_categories: 1,
        skipped: 2,
        errors: ["Row 3: duplicate dish name", "Row 5: bad price"],
      },
    });
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    await buttonsWith(wrapper, "stepDishes.csvImportBtn")[0].trigger("click");
    await nextTick();
    await setCsvFile(wrapper);
    await buttonsWith(wrapper, "stepDishes.csvImportSubmit")[0].trigger("click");
    await flushPromises();
    await flushPromises();

    expect(wrapper.text()).toContain("stepDishes.csvImportSuccess");
    expect(wrapper.text()).toContain(
      'stepDishes.csvImportCreatedCategories({"count":1})'
    );
    expect(wrapper.text()).toContain('stepDishes.csvImportSkipped({"count":2})');
    expect(wrapper.text()).toContain("stepDishes.csvImportErrorsTitle");
    expect(wrapper.text()).toContain("Row 3: duplicate dish name");
    expect(wrapper.text()).toContain("Row 5: bad price");
  });

  // ── A3-38: load failure keeps the local list + retry ───────────────────
  it("A3-38: a failed reload keeps local dishes and offers a retry", async () => {
    dishListMock.mockResolvedValue([serverDish()]);
    dishUpsertMock.mockRejectedValueOnce(new Error("save failed"));
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    await openQuickAdd(wrapper);
    await fillQuickDishName(wrapper, "New Dish");
    await submitQuickAdd(wrapper);
    expect(wrapper.text()).toContain("New Dish");

    // The import succeeds, but the reload it triggers fails (transient).
    dishListMock.mockRejectedValue(new Error("network down"));
    apiPostMock.mockResolvedValue({ data: { created_dishes: 1 } });
    await buttonsWith(wrapper, "stepDishes.csvImportBtn")[0].trigger("click");
    await nextTick();
    await setCsvFile(wrapper);
    await buttonsWith(wrapper, "stepDishes.csvImportSubmit")[0].trigger("click");
    await flushPromises();
    await flushPromises();

    expect(wrapper.text()).toContain("New Dish");
    expect(wrapper.text()).toContain("Soup");
    expect(buttonsWith(wrapper, "common.retry").length).toBeGreaterThan(0);

    // Retry with the server back: the list reloads and the retry goes away.
    dishListMock.mockResolvedValue([serverDish()]);
    await buttonsWith(wrapper, "common.retry")[0].trigger("click");
    await flushPromises();
    await flushPromises();
    expect(wrapper.text()).toContain("Soup");
    expect(buttonsWith(wrapper, "common.retry").length).toBe(0);
  });

  // ── A3-39: Unassigned filter chip ───────────────────────────────────────
  it("A3-39: the unassigned strip opens a filter that renders the orphan row", async () => {
    dishListMock.mockResolvedValue([
      serverDish({ id: 8, name: "Orphan Soup", category: "" }),
    ]);
    seedTenant();
    wrapper = mountDishes();
    await flushPromises();
    await flushPromises();

    expect(wrapper.text()).toContain("stepDishes.unassignedWarning");
    expect(wrapper.text()).not.toContain("Orphan Soup");

    await buttonsWith(wrapper, "stepDishes.unassignedWarning")[0].trigger("click");
    await nextTick();
    expect(wrapper.text()).toContain("Orphan Soup");
    expect(wrapper.text()).toContain("stepDishes.unassignedFilter");

    // Toggling the chip off hides the orphan again.
    await buttonsWith(wrapper, "stepDishes.unassignedFilter")[0].trigger("click");
    await nextTick();
    expect(wrapper.text()).not.toContain("Orphan Soup");
  });
});
