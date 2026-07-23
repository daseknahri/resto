/**
 * Unit tests for CartOrderSummary — the checkout order-summary breakdown extracted
 * from Cart.vue (RISK FE-2). Display only: it renders subtotal / loyalty / delivery-
 * fee / tip / wallet / total rows + the pre-order ETA from parent-computed pricing
 * props. It computes and mutates nothing (no payment, no order placement).
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({
    t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k),
  }),
}));
vi.mock("../AppIcon.vue", () => ({
  default: { name: "AppIcon", props: ["name"], template: "<span />" },
}));

import CartOrderSummary from "../CartOrderSummary.vue";

const base = {
  fulfillmentType: "delivery", subtotal: 100, deliveryFeeAmount: 10,
  deliveryFeeIsDistance: false, deliveryDistanceKm: 0, deliveryFeePending: false,
  deliveryOutOfRange: false, loyaltyDiscount: 0, tipAmount: 0, walletApplied: false,
  walletDeduction: 0, grandTotal: 110, checkoutEta: null, formatPrice: (n) => `$${n}`,
};

const mountIt = (props = {}) => mount(CartOrderSummary, { props: { ...base, ...props } });

describe("CartOrderSummary", () => {
  it("shows the subtotal + delivery fee rows for a delivery order with a fee", () => {
    const w = mountIt({ fulfillmentType: "delivery", deliveryFeeAmount: 10, subtotal: 100 });
    expect(w.text()).toContain("cartPage.subtotal");
    expect(w.text()).toContain("$100");
    expect(w.text()).toContain("cartPage.deliveryFee");
    expect(w.text()).toContain("$10");
  });

  it("shows a km hint when the delivery fee is distance-based", () => {
    const w = mountIt({ deliveryFeeAmount: 10, deliveryFeeIsDistance: true, deliveryDistanceKm: 3 });
    expect(w.text()).toContain("3 km");
  });

  it("shows the pending and free delivery-fee states", () => {
    expect(mountIt({ deliveryFeeAmount: 0, deliveryFeePending: true }).text()).toContain("cartPage.deliveryFeeByDistanceShort");
    expect(mountIt({ deliveryFeeAmount: 0, deliveryFeePending: false, deliveryOutOfRange: false }).text()).toContain("cartPage.free");
  });

  it("shows the loyalty discount, tip and wallet rows when present", () => {
    const w = mountIt({ loyaltyDiscount: 15, tipAmount: 8, walletApplied: true, walletDeduction: 20 });
    expect(w.text()).toContain("cartPage.loyaltyDiscount");
    expect(w.text()).toContain("-$15");
    expect(w.text()).toContain("cartPage.tipLabel");
    expect(w.text()).toContain("+$8");
    expect(w.text()).toContain("cartPage.payWithCredits");
    expect(w.text()).toContain("-$20");
  });

  it("always shows the grand total", () => {
    const w = mountIt({ grandTotal: 118 });
    expect(w.text()).toContain("cartPage.total");
    expect(w.text()).toContain("$118");
  });

  it("renders the pre-order ETA (delivery vs pickup) when present and in range", () => {
    expect(mountIt({ checkoutEta: { type: "delivery", min: 30, max: 45 } }).text())
      .toContain('cartPage.etaDelivery:{"min":30,"max":45}');
    expect(mountIt({ checkoutEta: { type: "pickup", min: 15, max: 20 } }).text())
      .toContain('menu.etaReadyIn:{"min":15,"max":20}');
    // hidden when out of range
    expect(mountIt({ checkoutEta: { type: "delivery", min: 30, max: 45 }, deliveryOutOfRange: true }).text())
      .not.toContain("cartPage.etaDelivery");
  });

  it("hides the subtotal + delivery-fee rows for a non-delivery order", () => {
    const w = mountIt({ fulfillmentType: "pickup", deliveryFeeAmount: 0 });
    expect(w.text()).not.toContain("cartPage.subtotal");
    expect(w.text()).not.toContain("cartPage.deliveryFee");
  });
});
