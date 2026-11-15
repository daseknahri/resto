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

// ── G4b-D additions ─────────────────────────────────────────────────────────
// Imports below are hoisted (ESM), so they may live at the end of the file.
import api from "../../lib/api";
import { useToastStore } from "../../stores/toast";
import { useConfirmModal } from "../../composables/useConfirmModal";

// B-25/B-26/B-27/B-28: delete confirms, load-failure toasts, single-PATCH
// stock save, auto-reset success toast, invalid-input error + revert.
describe("OwnerInventory — G4b-D (B-25, B-26, B-27, B-28)", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    _routes = {};
    vi.clearAllMocks();
  });

  afterEach(() => {
    _routes = {};
  });

  // The mocked t() returns the key verbatim, so toast assertions read the raw key.
  const toastSpy = () => {
    const spy = vi.spyOn(useToastStore(), "show");
    return spy;
  };

  const openIngredients = async () => {
    _routes = {
      "/owner/ingredients/": {
        data: [{ id: 11, name: "Flour", unit: "kg", stock_quantity: 12, low_stock_threshold: 5, is_low_stock: false, cost_per_unit: null }],
      },
      "/dishes/": { data: [] },
    };
    const wrapper = mountInv();
    await flushPromises();
    wrapper.vm.switchSubtab("ingredients");
    await flushPromises();
    expect(wrapper.text()).toContain("Flour");
    return wrapper;
  };

  // ── B-25: ingredient delete confirms ─────────────────────────────────────
  it("B-25: ingredient delete waits for the confirm and deletes on approval", async () => {
    const wrapper = await openIngredients();
    const btn = wrapper.find('[aria-label="common.delete Flour"]');
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();
    // No DELETE before the owner approves the confirm dialog.
    expect(api.delete).not.toHaveBeenCalled();
    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();
    expect(api.delete).toHaveBeenCalledWith("/owner/ingredients/11/");
    expect(wrapper.text()).not.toContain("Flour");
  });

  it("B-25: declining the ingredient-delete confirm deletes nothing", async () => {
    const wrapper = await openIngredients();
    await wrapper.find('[aria-label="common.delete Flour"]').trigger("click");
    await flushPromises();
    useConfirmModal()._settle(false);
    await flushPromises();
    expect(api.delete).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Flour");
  });

  // ── B-25: recipe-line delete confirms ────────────────────────────────────
  it("B-25: recipe-line delete waits for the confirm and deletes on approval", async () => {
    // NOTE: the recipe-lines route fragment must precede "/dishes/" — _match
    // returns the FIRST matching fragment and "/dishes/" is a substring of the
    // recipe URL.
    _routes = {
      "/owner/dishes/1/recipe/": {
        data: [{ id: 31, ingredient_name: "Flour", ingredient_unit: "kg", quantity: 0.5 }],
      },
      "/owner/ingredients/": {
        data: [{ id: 11, name: "Flour", unit: "kg", stock_quantity: 12, low_stock_threshold: 5, is_low_stock: false, cost_per_unit: null }],
      },
      "/dishes/": {
        data: [{ id: 1, name: "Tagine", is_published: true, is_available: true, stock_qty: 5 }],
      },
    };
    const wrapper = mountInv();
    await flushPromises();
    wrapper.vm.switchSubtab("recipes");
    await flushPromises();
    await wrapper.find("select").setValue(1);
    await flushPromises();
    expect(wrapper.text()).toContain("Flour");
    const btn = wrapper.find('[aria-label="common.delete Flour"]');
    expect(btn.exists()).toBe(true);
    await btn.trigger("click");
    await flushPromises();
    expect(api.delete).not.toHaveBeenCalled();
    useConfirmModal()._settle(true);
    await flushPromises();
    await flushPromises();
    expect(api.delete).toHaveBeenCalledWith("/owner/recipe-lines/31/");
    // The line's delete button is gone (the ingredient picker still lists
    // "Flour (kg)" as an addable ingredient, so a plain text check would lie).
    expect(wrapper.find('[aria-label="common.delete Flour"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain("× 0.5");
  });

  // ── B-26: load failures report as load failures ──────────────────────────
  it("B-26: ingredients load failure toasts ingLoadFailed, not saveFailed", async () => {
    const wrapper = mountInv();
    await flushPromises();
    const show = toastSpy();
    api.get.mockRejectedValueOnce(new Error("boom"));
    wrapper.vm.switchSubtab("ingredients");
    await flushPromises();
    expect(show).toHaveBeenCalledWith("inventory.ingLoadFailed", "error");
    expect(show).not.toHaveBeenCalledWith("inventory.saveFailed", expect.anything());
  });

  it("B-26: categories load failure toasts catLoadFailed, not catToggleFailed", async () => {
    const wrapper = mountInv();
    await flushPromises();
    const show = toastSpy();
    api.get.mockRejectedValueOnce(new Error("boom"));
    wrapper.vm.switchSubtab("categories");
    await flushPromises();
    expect(show).toHaveBeenCalledWith("inventory.catLoadFailed", "error");
    expect(show).not.toHaveBeenCalledWith("inventory.catToggleFailed", expect.anything());
  });

  it("B-26: recipe-lines load failure toasts recLoadFailed, not ingSaveFailed", async () => {
    _routes = {
      "/owner/ingredients/": { data: [] },
      "/dishes/": {
        data: [{ id: 1, name: "Tagine", is_published: true, is_available: true, stock_qty: 5 }],
      },
    };
    const wrapper = mountInv();
    await flushPromises();
    wrapper.vm.switchSubtab("recipes");
    await flushPromises();
    const show = toastSpy();
    api.get.mockRejectedValueOnce(new Error("boom"));
    await wrapper.find("select").setValue(1);
    await flushPromises();
    expect(show).toHaveBeenCalledWith("inventory.recLoadFailed", "error");
    expect(show).not.toHaveBeenCalledWith("inventory.ingSaveFailed", expect.anything());
  });

  // ── B-27: single-PATCH stock save + auto-reset success toast ─────────────
  it("B-27: restocking a sold-out dish sends ONE PATCH with stock + availability", async () => {
    _routes = {
      "/dishes/": {
        data: [
          { id: 1, name: "Tagine", is_published: true, is_available: false, stock_qty: 0, low_stock_threshold: 3, category_name: "Mains" },
        ],
      },
    };
    const wrapper = mountInv();
    await flushPromises();
    await wrapper.find("#inv-stock-1").setValue("5");
    await wrapper.find("#inv-stock-1").trigger("change");
    // commitStock debounces the PATCH by 600ms.
    await new Promise((r) => setTimeout(r, 750));
    await flushPromises();
    expect(api.patch).toHaveBeenCalledTimes(1);
    expect(api.patch).toHaveBeenCalledWith("/dishes/1/", { stock_qty: 5, is_available: true });
    // The dish reads available again — the sold-out badge is gone.
    expect(wrapper.text()).not.toContain("inventory.soldOut");
  });

  it("B-27: threshold-only change sends ONE PATCH with just the threshold", async () => {
    _routes = {
      "/dishes/": {
        data: [
          { id: 1, name: "Tagine", is_published: true, is_available: true, stock_qty: 5, low_stock_threshold: 3, category_name: "Mains" },
        ],
      },
    };
    const wrapper = mountInv();
    await flushPromises();
    await wrapper.find("#inv-thresh-1").setValue("7");
    await wrapper.find("#inv-thresh-1").trigger("change");
    await new Promise((r) => setTimeout(r, 750));
    await flushPromises();
    expect(api.patch).toHaveBeenCalledTimes(1);
    expect(api.patch).toHaveBeenCalledWith("/dishes/1/", { low_stock_threshold: 7 });
  });

  it("B-27: auto-reset toggle toasts success (was silent on success)", async () => {
    _routes = { "/dishes/": { data: [] } };
    const wrapper = mountInv();
    await flushPromises();
    const show = toastSpy();
    // The auto-reset switch is the only role="switch" on the dish-stock tab.
    await wrapper.find('button[role="switch"]').trigger("click");
    await flushPromises();
    expect(api.patch).toHaveBeenCalledWith("/profile/", { auto_reset_availability: true });
    expect(show).toHaveBeenCalledWith("inventory.autoResetEnabled", "success");
  });

  // ── B-28: invalid stock/threshold input errors and reverts ───────────────
  it("B-28: negative stock shows an error, sends no PATCH, and reverts the input", async () => {
    _routes = {
      "/dishes/": {
        data: [
          { id: 1, name: "Tagine", is_published: true, is_available: true, stock_qty: 5, low_stock_threshold: 3, category_name: "Mains" },
        ],
      },
    };
    const wrapper = mountInv();
    await flushPromises();
    const show = toastSpy();
    const input = wrapper.find("#inv-stock-1");
    await input.setValue("-3");
    await input.trigger("change");
    await flushPromises();
    expect(show).toHaveBeenCalledWith("inventory.invalidQty", "error");
    expect(api.patch).not.toHaveBeenCalled();
    // The rejected value must not linger in the input.
    expect(input.element.value).toBe("5");
  });

  it("B-28: negative threshold shows an error, sends no PATCH, and reverts the input", async () => {
    _routes = {
      "/dishes/": {
        data: [
          { id: 1, name: "Tagine", is_published: true, is_available: true, stock_qty: 5, low_stock_threshold: 3, category_name: "Mains" },
        ],
      },
    };
    const wrapper = mountInv();
    await flushPromises();
    const show = toastSpy();
    const input = wrapper.find("#inv-thresh-1");
    await input.setValue("-2");
    await input.trigger("change");
    await flushPromises();
    expect(show).toHaveBeenCalledWith("inventory.invalidQty", "error");
    expect(api.patch).not.toHaveBeenCalled();
    expect(input.element.value).toBe("3");
  });
});
