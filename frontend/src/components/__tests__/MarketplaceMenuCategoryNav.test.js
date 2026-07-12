/**
 * Unit tests for MarketplaceMenuCategoryNav — the sticky category-tabs /
 * search / allergen-filter navigation strip of MarketplaceMenuPage.vue
 * (customer menu-browsing page), extracted into a standalone presentational
 * component (RISK FE-2). This component holds no cart, add-to-cart, or money
 * logic; it only renders what it's given and forwards user intent (select a
 * category, type/clear the search box, toggle an allergen chip) via emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));

import MarketplaceMenuCategoryNav from "../MarketplaceMenuCategoryNav.vue";

const mountComp = (props = {}) =>
  mount(MarketplaceMenuCategoryNav, {
    props: {
      categories: [],
      activeCategoryId: null,
      searchQuery: "",
      isSearchActive: false,
      availableAllergens: [],
      selectedAllergens: [],
      allergenHiddenCount: 0,
      ...props,
    },
  });

describe("MarketplaceMenuCategoryNav", () => {
  it("renders no buttons when there is one category, no active search, and no allergens", () => {
    const w = mountComp({ categories: [{ id: 1, name: "Mains" }] });
    expect(w.findAll("button").length).toBe(0);
  });

  it("renders a button per category once there are 2+, and highlights the active one", () => {
    const w = mountComp({
      categories: [{ id: 1, name: "Mains" }, { id: 2, name: "Drinks" }],
      activeCategoryId: 2,
    });
    const buttons = w.findAll("button");
    expect(buttons.length).toBe(2);
    expect(buttons[0].text()).toBe("Mains");
    expect(buttons[1].text()).toBe("Drinks");
    expect(buttons[1].classes().join(" ")).toContain("text-slate-950");
    expect(buttons[0].classes().join(" ")).not.toContain("text-slate-950");
  });

  it("emits select-category with the clicked category's id", async () => {
    const w = mountComp({
      categories: [{ id: 1, name: "Mains" }, { id: 2, name: "Drinks" }],
    });
    await w.findAll("button")[0].trigger("click");
    expect(w.emitted("select-category")).toEqual([[1]]);
  });

  it("binds the search input to searchQuery and emits search-input with the raw typed value", async () => {
    const w = mountComp({ searchQuery: "piz" });
    const input = w.find('input[type="search"]');
    expect(input.element.value).toBe("piz");
    await input.setValue("pizza");
    expect(w.emitted("search-input")).toEqual([["pizza"]]);
  });

  it("hides the clear-search button when isSearchActive is false", () => {
    const w = mountComp({ isSearchActive: false });
    expect(w.find('[aria-label="mktMenu.searchClear"]').exists()).toBe(false);
  });

  it("shows the clear-search button and emits clear-search when clicked", async () => {
    const w = mountComp({ isSearchActive: true, searchQuery: "abc" });
    const clearBtn = w.find('[aria-label="mktMenu.searchClear"]');
    expect(clearBtn.exists()).toBe(true);
    await clearBtn.trigger("click");
    expect(w.emitted("clear-search")).toBeTruthy();
  });

  it("does not render the allergen strip when there are no available allergens", () => {
    const w = mountComp({ availableAllergens: [] });
    expect(w.find('[role="group"]').exists()).toBe(false);
  });

  it("renders an allergen chip per available allergen reflecting selected state", () => {
    const w = mountComp({
      availableAllergens: ["nuts", "dairy"],
      selectedAllergens: ["nuts"],
    });
    const group = w.find('[role="group"]');
    expect(group.exists()).toBe(true);
    const chips = group.findAll("button");
    expect(chips.length).toBe(2);
    expect(chips[0].attributes("aria-pressed")).toBe("true");
    expect(chips[1].attributes("aria-pressed")).toBe("false");
  });

  it("emits toggle-allergen with the clicked allergen", async () => {
    const w = mountComp({ availableAllergens: ["nuts", "dairy"] });
    const chips = w.find('[role="group"]').findAll("button");
    await chips[1].trigger("click");
    expect(w.emitted("toggle-allergen")).toEqual([["dairy"]]);
  });

  it("shows the hidden-count badge only when allergenHiddenCount is greater than 0", () => {
    const w0 = mountComp({ availableAllergens: ["nuts"], allergenHiddenCount: 0 });
    expect(w0.text()).not.toContain("mktMenu.allergenHidden");

    const w3 = mountComp({ availableAllergens: ["nuts"], allergenHiddenCount: 3 });
    expect(w3.text()).toContain('mktMenu.allergenHidden:{"n":3}');
  });
});
