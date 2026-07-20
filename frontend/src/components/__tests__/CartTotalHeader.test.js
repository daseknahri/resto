/**
 * Unit tests for CartTotalHeader — the compact total header of Cart.vue's checkout
 * panel (RISK FE-2). Display only: the grand-total figure, item-count label and
 * fulfillment caption from parent-computed props. Computes/mutates nothing.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({ useI18n: () => ({ t: (k) => k }) }));

import CartTotalHeader from "../CartTotalHeader.vue";

const mountIt = (props = {}) =>
  mount(CartTotalHeader, {
    props: { grandTotal: 110, countLabel: "3 items", fulfillmentType: "delivery", formatPrice: (n) => `$${n}`, ...props },
  });

describe("CartTotalHeader", () => {
  it("renders the total label, formatted grand total and count label", () => {
    const w = mountIt({ grandTotal: 110, countLabel: "3 items" });
    expect(w.text()).toContain("cartPage.total");
    expect(w.text()).toContain("$110");
    expect(w.text()).toContain("3 items");
  });

  it("shows the delivery caption for a delivery order and pickup otherwise", () => {
    expect(mountIt({ fulfillmentType: "delivery" }).text()).toContain("cartPage.delivery");
    expect(mountIt({ fulfillmentType: "pickup" }).text()).toContain("cartPage.pickup");
  });

  it("hides the fulfillment caption when there is no fulfillment type", () => {
    const w = mountIt({ fulfillmentType: "" });
    expect(w.text()).not.toContain("cartPage.delivery");
    expect(w.text()).not.toContain("cartPage.pickup");
  });
});
