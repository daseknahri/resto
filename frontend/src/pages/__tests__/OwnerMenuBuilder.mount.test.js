/**
 * Mount smoke test for OwnerMenuBuilder.vue (the owner's menu-builder shell, ~424 lines).
 *
 * WHY: the app's recurring production bug class is "a page white-screens on load
 * because a setup()-time error (TDZ, undefined-map access, bad import) was never
 * caught by a test". This page is exposed to it: its setup() wires several
 * composables + two Pinia stores, and its template eagerly evaluates a
 * `draftDishCount` computed that does `Object.values(menuStore.dishes).flat()...`
 * on first render (via the dishes-tab badge in the tabs v-for). Mounting the real
 * setup() here makes any such crash fail CI instead of in production.
 *
 * NOTE ON API: unlike most owner pages, OwnerMenuBuilder has NO onMounted and
 * fires NO api GET at mount. `lib/api` is imported only for the user-triggered CSV
 * `runImport` POST (/owner/menu/import/). So there is no mount-time network to
 * drive — the "loaded" state is seeded into the REAL menu store (dishes) instead.
 * The category/dish LISTS are rendered by child components (StepCategories /
 * StepDishes / OwnerInventory) which shallowMount stubs; the page's OWN
 * data-driven template output is the draft-count badge, so that is the loaded
 * assertion.
 *
 * Pattern-faithful to pages/__tests__/OwnerHome.mount.test.js +
 * MarketplaceMenuPage.mount.test.js:
 *   - shallowMount (auto-stubs AppIcon, TemplatePickerModal, and the dynamic
 *     <component :is> tab bodies: StepSuperCategories/StepCategories/StepDishes/
 *     OwnerInventory)
 *   - real pinia (menu + toast stores run for real)
 *   - useI18n + useVocabulary + vue-router mocked; lib/api mocked
 *
 * The page imports NO RouterLink (template uses a plain <a href="/menu">), so no
 * vi.hoisted stub is needed; a harmless global.stubs.RouterLink is kept for
 * parity. No intervals/observers/WebSocket/scrollIntoView run at mount, so no
 * timer cleanup is strictly required — afterEach unmount is kept for hygiene.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// useI18n destructure in the page is `{ t }` ONLY.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
  }),
}));

// The page destructures `{ itemPlural, groupPlural }` (both computed refs) — mock
// them as plain { value } so the tabs computed + h2 title render deterministically
// without dragging in the tenant store. Mirrors MarketplaceMenuPage's useVocabulary mock.
vi.mock("../../composables/useVocabulary", () => ({
  useVocabulary: () => ({
    itemPlural: { value: "Items" },
    groupPlural: { value: "Categories" },
  }),
}));

// lib/api: imported for the CSV import POST only (no mount-time GET). Mock the
// whole surface so the real axios instance never loads.
vi.mock("../../lib/api", () => ({
  // shared canonical extractor (added to lib/api; mock returns the fallback)
  extractApiErrorMessage: (err, fallback = "") => fallback,
  default: {
    get: vi.fn(() => Promise.resolve({ data: {} })),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
    defaults: { baseURL: "/api" },
  },
}));

// The page imports { useRoute, useRouter } from vue-router. route.query.tab is
// read at setup (defaults to "dishes"); router.replace only fires on a tab click.
vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {}, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import OwnerMenuBuilder from "../OwnerMenuBuilder.vue";
import { useMenuStore } from "../../stores/menu";

const mountBuilder = () =>
  shallowMount(OwnerMenuBuilder, {
    global: {
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        Transition: { template: "<slot />" },
        Teleport: { template: "<slot />" },
      },
    },
  });

describe("OwnerMenuBuilder — mount smoke", () => {
  let wrapper;

  beforeEach(() => {
    // Menu store touches the staleCache (localStorage-backed) lib on its fetch
    // paths; clear it so no cross-test bleed even though this page never fetches.
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  // ── (1) empty / default mount ─────────────────────────────────────────────
  // The core guard: real setup() + first render (tabs v-for, draftDishCount over
  // an empty dishes map, the toolbar) must not throw with default/empty state.
  it("mounts with empty/default state without a setup() crash", async () => {
    expect(() => {
      wrapper = mountBuilder();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Own-template, own-namespace anchor: the always-rendered "Import CSV" toolbar
    // control → t("ownerMenuBuilder.importCsv"). The mocked t echoes the key.
    expect(wrapper.text()).toContain("ownerMenuBuilder.importCsv");
  });

  // ── (2) loaded state: unpublished dishes in the store → draft badge ────────
  // Seeds the REAL menu store so draftDishCount > 0, exercising the page's own
  // data-driven template branch (the dishes-tab draft badge in the tabs v-for).
  it("mounts with loaded menu data (unpublished dishes) and renders the draft badge", async () => {
    const menuStore = useMenuStore();
    // One published + one hidden dish across a category → draftDishCount === 1.
    menuStore.dishes = {
      starters: [
        { id: 1, name: "Tagine", is_published: true },
        { id: 2, name: "Couscous", is_published: false },
      ],
    };

    expect(() => {
      wrapper = mountBuilder();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Loaded assertion: the draft badge only renders when draftDishCount > 0.
    // Its aria-label is t("ownerMenuBuilder.draftBadgeLabel", { count }) and its
    // text is the count itself.
    expect(wrapper.html()).toContain("ownerMenuBuilder.draftBadgeLabel");
    expect(wrapper.text()).toContain("ownerMenuBuilder.importCsv");
  });
});

// ── B-12: CSV import refresh (Run 8 S1-E, appended — base tests above untouched)
// After a successful CSV import the dish list must refresh: runImport now
// force-refreshes the menu store (fetchCategories(true)) and bumps reloadKey
// (remounting the active tab, whose onMounted load() refetches). The store
// refresh is the observable half in this harness — the tab bodies are stubbed
// by shallowMount, so the remount itself is covered by the same one-line
// reloadKey pattern onTemplateApplied already uses; the assertions below prove
// the new success-path block ran (store refetched) and that it is gated on
// something actually being imported.
// FE lessons applied: setValue is not used on the file input — files are set
// via defineProperty + trigger("change"); the :disabled-bound Import button is
// only clicked after the change tick, never after setting wrapper.vm state.
describe("OwnerMenuBuilder - CSV import refresh (B-12)", () => {
  let wrapper;
  let api;

  beforeEach(async () => {
    localStorage.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
    api = (await import("../../lib/api")).default;
  });

  afterEach(() => {
    if (wrapper) wrapper.unmount();
    wrapper = undefined;
  });

  const openImport = async () => {
    wrapper = mountBuilder();
    await flushPromises();
    const toolbarBtn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("ownerMenuBuilder.importCsv"));
    expect(toolbarBtn?.exists()).toBe(true);
    await toolbarBtn.trigger("click");
    await flushPromises();
  };

  const pickFile = async () => {
    const input = wrapper.find('input[type="file"]');
    expect(input.exists()).toBe(true);
    const file = new File(
      ["category_name,dish_name,description,price,tags,allergens\nStarters,Tagine,,12,,,"],
      "menu.csv",
      { type: "text/csv" }
    );
    Object.defineProperty(input.element, "files", { value: [file] });
    await input.trigger("change");
    await flushPromises();
  };

  const clickImportStart = async () => {
    const btn = wrapper
      .findAll("button")
      .find((b) => b.text().includes("ownerMenuBuilder.importStart"));
    expect(btn?.exists()).toBe(true);
    // Guard (FE lesson): never click a :disabled-bound button without a tick
    // after the state change — the change tick above already ran, so the
    // button must be enabled here.
    expect(btn.attributes("disabled")).toBeUndefined();
    await btn.trigger("click");
    await flushPromises();
  };

  it("refreshes the menu store after a successful import (dishes created)", async () => {
    const menuStore = useMenuStore();
    menuStore.dishes = {
      starters: [{ id: 1, name: "Old Dish", is_published: true }],
    };
    api.post.mockResolvedValueOnce({
      data: { created_dishes: 3, created_categories: 1, skipped: 0, errors: [] },
    });

    await openImport();
    await pickFile();
    await clickImportStart();

    // Results panel renders the import outcome.
    expect(wrapper.text()).toContain("ownerMenuBuilder.resultDishes");
    // Store was force-refreshed: the mocked GETs return no categories, so the
    // seeded stale dishes are replaced by the fresh (empty) fetch result.
    expect(menuStore.dishes).toEqual({});
    expect(api.get).toHaveBeenCalledWith(
      "/categories/",
      expect.objectContaining({ params: { force_locale: 1 } })
    );
  });

  it("does not refresh when the import creates nothing", async () => {
    const menuStore = useMenuStore();
    menuStore.dishes = {
      starters: [{ id: 1, name: "Old Dish", is_published: true }],
    };
    api.post.mockResolvedValueOnce({
      data: { created_dishes: 0, created_categories: 0, skipped: 2, errors: [] },
    });

    await openImport();
    await pickFile();
    await clickImportStart();

    expect(wrapper.text()).toContain("ownerMenuBuilder.resultDishes");
    // No-op import: store untouched, no refetch fired.
    expect(menuStore.dishes).toEqual({
      starters: [{ id: 1, name: "Old Dish", is_published: true }],
    });
    expect(api.get).not.toHaveBeenCalled();
  });
});
