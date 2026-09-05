/**
 * Mount smoke test for OwnerInventory.vue (owner menu/inventory management).
 *
 * WHY: this big four-sub-tab component had NO mount test. The app's recurring
 * production bug class is "a page white-screens on load because a setup()-time
 * error (TDZ, undefined map access, bad import) was never caught by a test".
 * Mounting runs the real setup(); switching each sub-tab renders each template
 * branch — so a crash in any branch fails CI here instead of in production.
 *
 * Pattern-faithful to pages/__tests__/MarketplaceMenuPage.mount.test.js +
 * pages/__tests__/Marketplace.loadMore.test.js (URL-routed api mock):
 *   - shallowMount (auto-stubs the AppIcon child)
 *   - real pinia (tenant + toast stores run for real) + a mocked lib/api
 *   - useI18n mocked to deterministic keys
 * OwnerInventory has no vue-router usage, so no router mock is needed.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { shallowMount, flushPromises } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}(${JSON.stringify(p)})` : k),
    formatNumber: (v) => String(v),
    formatCurrency: (v) => String(v),
    currentLocale: { value: "en" },
  }),
}));

// URL-routed api mock. Default: every GET resolves empty; writes resolve empty.
// Tests set _routes before mount / before a sub-tab switch to drive loaded states.
let _routes = {};
const _match = (url) => {
  const hit = Object.keys(_routes).find((frag) => url.includes(frag));
  return hit ? _routes[hit] : { data: {} };
};
vi.mock("../../lib/api", () => ({
  default: {
    get: vi.fn((url) => Promise.resolve(_match(url))),
    post: vi.fn(() => Promise.resolve({ data: {} })),
    patch: vi.fn(() => Promise.resolve({ data: {} })),
    delete: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

import OwnerInventory from "../OwnerInventory.vue";

const mountInv = () =>
  shallowMount(OwnerInventory, {
    global: {
      stubs: {
        Transition: { template: "<slot />" },
      },
    },
  });

describe("OwnerInventory — mount smoke", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    _routes = {};
  });

  // ── (1) default mount → dish-stock empty state ────────────────────────────
  it("mounts without a setup() crash and shows the dish-stock empty state", async () => {
    let wrapper;
    expect(() => {
      wrapper = mountInv();
    }).not.toThrow();

    await flushPromises();
    expect(wrapper.exists()).toBe(true);
    // Sub-tab bar rendered.
    expect(wrapper.text()).toContain("inventory.subtabDishStock");
    // No dishes loaded → empty state.
    expect(wrapper.text()).toContain("inventory.empty");
  });

  // ── (2) loaded dish stock ─────────────────────────────────────────────────
  // Drives the `filtered` computed (isLow() + the sold-out / low / normal sort
  // weighting) over a realistic payload — the classic per-row map path.
  it("renders dish rows and exercises the isLow()/sort path", async () => {
    _routes = {
      "/dishes/": {
        data: [
          { id: 1, name: "Sold Out Dish", is_published: true, is_available: false, stock_qty: 0, low_stock_threshold: 3, category_name: "Mains" },
          { id: 2, name: "Low Stock Dish", is_published: true, is_available: true, stock_qty: 2, low_stock_threshold: 5, category_name: "Sides" },
          { id: 3, name: "Plenty Dish", is_published: true, is_available: true, stock_qty: 40, low_stock_threshold: 3, category_name: "Drinks" },
          { id: 4, name: "Draft Dish", is_published: false, is_available: true, stock_qty: null, low_stock_threshold: null, category_name: "Hidden" },
        ],
      },
    };

    let wrapper;
    expect(() => {
      wrapper = mountInv();
    }).not.toThrow();
    await flushPromises();

    const text = wrapper.text();
    // Published dishes render; the draft (is_published:false) is filtered out.
    expect(text).toContain("Sold Out Dish");
    expect(text).toContain("Low Stock Dish");
    expect(text).toContain("Plenty Dish");
    expect(text).not.toContain("Draft Dish");
  });

  // ── (3) each sub-tab renders without throwing ─────────────────────────────
  // The four sub-tabs are independent template branches, each with its own refs
  // and lazy fetch. Rendering all four guards against an undefined-ref crash in
  // any branch (the exact white-screen class this test exists for).
  it("switches through ingredients / categories / recipes sub-tabs without a crash", async () => {
    _routes = {
      "/owner/ingredients/": { data: [{ id: 11, name: "Flour", unit: "kg", stock_quantity: 12, low_stock_threshold: 5, is_low_stock: false, cost_per_unit: null }] },
      "/categories/": { data: [{ id: 21, name: "Mains", is_temporarily_disabled: false, super_category_name: null }] },
      "/dishes/": { data: [{ id: 1, name: "Tagine", is_published: true, is_available: true, stock_qty: 5 }] },
    };

    const wrapper = mountInv();
    await flushPromises();

    // Ingredients branch.
    expect(() => wrapper.vm.switchSubtab("ingredients")).not.toThrow();
    await flushPromises();
    expect(wrapper.text()).toContain("inventory.ingTitle");
    expect(wrapper.text()).toContain("Flour");

    // Categories branch.
    expect(() => wrapper.vm.switchSubtab("categories")).not.toThrow();
    await flushPromises();
    expect(wrapper.text()).toContain("inventory.catPauseTitle");
    expect(wrapper.text()).toContain("Mains");

    // Recipes branch (dish picker; no dish selected yet).
    expect(() => wrapper.vm.switchSubtab("recipes")).not.toThrow();
    await flushPromises();
    expect(wrapper.text()).toContain("inventory.recPickDish");
  });
});
