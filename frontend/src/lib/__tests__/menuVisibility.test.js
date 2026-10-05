/**
 * countCustomerVisible mirrors the public menu's visibility rule (backend/menu/visibility.py).
 * The onboarding publish readiness check used to count every row of the owner's preview-mode
 * lists, so a menu whose only section was hidden/paused looked "ready to publish".
 */
import { describe, it, expect } from "vitest";
import { countCustomerVisible } from "../menuVisibility";

const section = (over = {}) => ({ id: 1, is_published: true, is_temporarily_disabled: false, ...over });
const category = (over = {}) => ({ id: 10, super_category: 1, is_published: true, is_temporarily_disabled: false, ...over });
const dish = (over = {}) => ({ id: 100, category: 10, is_published: true, ...over });

describe("countCustomerVisible", () => {
  it("counts a fully published section → category → dish chain", () => {
    expect(countCustomerVisible({ superCategories: [section()], categories: [category()], dishes: [dish()] }))
      .toEqual({ categories: 1, dishes: 1 });
  });

  it("hides everything under a paused section", () => {
    expect(countCustomerVisible({
      superCategories: [section({ is_temporarily_disabled: true })],
      categories: [category()],
      dishes: [dish()],
    })).toEqual({ categories: 0, dishes: 0 });
  });

  it("hides everything under an unpublished section", () => {
    expect(countCustomerVisible({
      superCategories: [section({ is_published: false })],
      categories: [category()],
      dishes: [dish()],
    })).toEqual({ categories: 0, dishes: 0 });
  });

  it("hides a paused or unpublished category and its dishes", () => {
    expect(countCustomerVisible({
      superCategories: [section()],
      categories: [category({ is_temporarily_disabled: true }), category({ id: 11, is_published: false })],
      dishes: [dish(), dish({ id: 101, category: 11 })],
    })).toEqual({ categories: 0, dishes: 0 });
  });

  it("skips an unpublished dish but keeps its visible category", () => {
    expect(countCustomerVisible({
      superCategories: [section()],
      categories: [category()],
      dishes: [dish({ is_published: false }), dish({ id: 101 })],
    })).toEqual({ categories: 1, dishes: 1 });
  });

  it("matches ids across number/string forms (select values are strings)", () => {
    expect(countCustomerVisible({
      superCategories: [section({ id: 2 })],
      categories: [category({ super_category: "2" })],
      dishes: [dish({ category: "10" })],
    })).toEqual({ categories: 1, dishes: 1 });
  });

  it("is safe with missing / non-array inputs", () => {
    expect(countCustomerVisible()).toEqual({ categories: 0, dishes: 0 });
    expect(countCustomerVisible({ superCategories: null, categories: {}, dishes: undefined }))
      .toEqual({ categories: 0, dishes: 0 });
  });
});
