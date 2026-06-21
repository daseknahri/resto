/**
 * Unit tests for QuickAddSheet — the quick-modifier sheet that adds (or, in
 * edit mode, replaces) a cart line. Covers the two CART-EDIT features:
 *   1. Edit-in-place mode seeds from initialOptionIds/qty/note and emits `save`.
 *   2. Per-item special-instructions textarea carries text onto the line note.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { setActivePinia, createPinia } from "pinia";

// Deterministic i18n: keys pass through; price formatting is trivial.
vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k) => k, formatPrice: (v) => `$${Number(v).toFixed(2)}` }),
}));

import QuickAddSheet from "../QuickAddSheet.vue";
import { useCartStore } from "../../stores/cart";

const DISH = {
  slug: "burger",
  name: "Burger",
  price: 10,
  currency: "MAD",
  options: [],
  option_groups: [
    {
      id: 1,
      name: "Size",
      min_select: 1,
      max_select: 1,
      options: [
        { id: 11, name: "Small", price_delta: 0 },
        { id: 12, name: "Large", price_delta: 2 },
      ],
    },
    {
      id: 2,
      name: "Extras",
      min_select: 0,
      max_select: 2,
      options: [
        { id: 21, name: "Cheese", price_delta: 1 },
        { id: 22, name: "Bacon", price_delta: 3 },
      ],
    },
  ],
};

const mountSheet = (props = {}) =>
  mount(QuickAddSheet, { props: { dish: DISH, currency: "MAD", ...props } });

describe("QuickAddSheet — add mode (special instructions)", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("carries special instructions onto the cart line note and key", async () => {
    const cart = useCartStore();
    const w = mountSheet();
    await w.find("textarea").setValue("no onions");
    await w.find("button.ui-btn-primary").trigger("click");

    expect(cart.items).toHaveLength(1);
    expect(cart.items[0].note).toBe("no onions");
    // note is folded into the key so two same-option lines stay distinct
    expect(cart.items[0].key).toContain("no onions");
  });

  it("pre-selects the first required option so a one-tap add works", () => {
    const w = mountSheet();
    // Size is required (min_select 1) -> first option pre-selected, no warning.
    expect(w.find(".ui-btn-primary").attributes("disabled")).toBeUndefined();
  });
});

describe("QuickAddSheet — edit mode", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("seeds qty, options and note from the initial line", () => {
    const w = mountSheet({
      mode: "edit",
      editKey: "burger::12,21::no onions",
      initialOptionIds: [12, 21],
      initialQty: 3,
      initialNote: "no onions",
    });
    // qty seeded
    expect(w.text()).toContain("3");
    // special-instructions textarea seeded
    expect(w.find("textarea").element.value).toBe("no onions");
    // button shows the save-changes label, not add-to-cart
    expect(w.find(".ui-btn-primary").text()).toContain("dishPage.saveChanges");
  });

  it("emits save with the original key and a rebuilt line, without calling add()", async () => {
    const cart = useCartStore();
    const w = mountSheet({
      mode: "edit",
      editKey: "burger::11::",
      initialOptionIds: [11],
      initialQty: 1,
      initialNote: "",
    });
    await w.find("button.ui-btn-primary").trigger("click");

    // edit mode emits `save` and must NOT add a new line directly to the cart
    expect(cart.items).toHaveLength(0);
    const saved = w.emitted("save");
    expect(saved).toBeTruthy();
    expect(saved[0][0].oldKey).toBe("burger::11::");
    expect(saved[0][0].line.slug).toBe("burger");
    expect(saved[0][0].line.option_ids).toEqual([11]);
  });

  it("does not pre-fill the textarea when the stored note is an options summary", () => {
    // The component skips notes beginning with the localized "Options:" prefix.
    // Under the mocked i18n, t('dishPage.options') === 'dishPage.options', so the
    // auto-generated summary the app produces would start with that token.
    const w = mountSheet({
      mode: "edit",
      editKey: "burger::12::",
      initialOptionIds: [12],
      initialQty: 1,
      initialNote: "dishPage.options: Large (+$2.00)",
    });
    expect(w.find("textarea").element.value).toBe("");
  });
});
