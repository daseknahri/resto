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
