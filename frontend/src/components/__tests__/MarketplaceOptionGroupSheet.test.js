/**
 * Unit tests for MarketplaceOptionGroupSheet — the dish option-group selection
 * bottom sheet extracted from MarketplaceMenuPage.vue as a PRESENTATIONAL child
 * (RISK FE-2). The parent keeps all selection state + logic; here we verify the
 * render, the selection helpers driving the UI, and the toggle/confirm/close emits.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import MarketplaceOptionGroupSheet from "../MarketplaceOptionGroupSheet.vue";

const dish = {
  name: "Burger",
  price: 50,
  image_url: "",
  tags: ["veg"],
  description: "Tasty",
  allergens: ["gluten"],
  option_groups: [
    {
      id: 1,
      name: "Size",
      min_select: 1,
      max_select: 1,
      options: [
        { id: 11, name: "Regular", price_delta: 0, is_available: true },
        { id: 12, name: "Large", price_delta: 10, is_available: true },
      ],
    },
  ],
};

const baseProps = {
  dish,
  flashSalePct: 0,
  showErrors: false,
  valid: false,
  unitPrice: 50,
  fmtPrice: (p) => `$${Number(p).toFixed(2)}`,
  dishSalePrice: (p) => Number(p) * 0.8,
  tagBadgeClass: () => "tag-class",
  isOptionSelected: () => false,
  isGroupAtMax: () => false,
};

const mountIt = (props = {}) =>
  mount(MarketplaceOptionGroupSheet, { props: { ...baseProps, ...props } });

describe("MarketplaceOptionGroupSheet", () => {
  it("renders the dish name, group + options, and the confirm price", () => {
    const w = mountIt();
    expect(w.text()).toContain("Burger");
    expect(w.text()).toContain("Size");
    expect(w.text()).toContain("Regular");
    expect(w.text()).toContain("Large");
    expect(w.text()).toContain("+$10.00"); // price_delta on the Large option
    expect(w.text()).toContain('mktMenu.optionConfirm:{"price":"$50.00"}');
  });

  it("reflects the selection helper via aria-pressed and disables when a group is at max", () => {
    const w = mountIt({ isOptionSelected: (g, o) => o === 11, isGroupAtMax: () => true });
    const optionBtns = w.findAll('button[aria-pressed]');
    expect(optionBtns[0].attributes("aria-pressed")).toBe("true"); // Regular selected
    expect(optionBtns[1].attributes("aria-pressed")).toBe("false");
    // Large is unselected AND the group is at max → disabled.
    expect(optionBtns[1].attributes("disabled")).toBeDefined();
  });

  it("emits toggle with (group, optionId) when an option is tapped", async () => {
    const w = mountIt();
    await w.findAll('button[aria-pressed]')[1].trigger("click"); // Large
    expect(w.emitted("toggle")[0][0].id).toBe(1);   // the group
    expect(w.emitted("toggle")[0][1]).toBe(12);      // the option id
  });

  it("emits confirm from the CTA and close from the X / backdrop / esc", async () => {
    const w = mountIt();
    const confirm = w.findAll("button").at(-1);
    await confirm.trigger("click");
    expect(w.emitted("confirm")).toBeTruthy();

    await w.find('button[aria-label="common.close"]').trigger("click");
    await w.find('[aria-hidden="true"].absolute').trigger("click"); // backdrop
    await w.find('[role="dialog"]').trigger("keydown.esc");
    expect(w.emitted("close").length).toBe(3);
  });

  it("shows the validation error only when showErrors && !valid", () => {
    expect(mountIt({ showErrors: true, valid: false }).find('[role="alert"]').exists()).toBe(true);
    expect(mountIt({ showErrors: true, valid: true }).find('[role="alert"]').exists()).toBe(false);
    expect(mountIt({ showErrors: false, valid: false }).find('[role="alert"]').exists()).toBe(false);
  });

  it("shows the flash-sale strikethrough base price when flashSalePct is set", () => {
    const w = mountIt({ flashSalePct: 20 });
    expect(w.find(".line-through").exists()).toBe(true);
    expect(w.find(".line-through").text()).toContain("$50.00"); // base price struck through
  });
});
