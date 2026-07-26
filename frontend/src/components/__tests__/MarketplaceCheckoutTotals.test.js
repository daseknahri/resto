/**
 * Unit tests for MarketplaceCheckoutTotals — the order-totals panel of the
 * Marketplace checkout drawer, a DISPLAY-ONLY child (RISK FE-2). Every value is
 * parent-computed; here we verify the rows render per state.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import MarketplaceCheckoutTotals from "../MarketplaceCheckoutTotals.vue";

const base = {
  prepEta: null, cartTotal: 100, fulfillmentType: "pickup", deliveryFeeIsDistance: false,
  deliveryDistanceKm: 0, deliveryIsFree: false, deliveryFee: 0, flashSaleDiscount: 0,
  flashSalePct: 0, loyaltyDiscount: 0, orderTotal: 100, fmtPrice: (n) => `$${Number(n).toFixed(2)}`,
};
const mountIt = (props = {}) => mount(MarketplaceCheckoutTotals, { props: { ...base, ...props } });

describe("MarketplaceCheckoutTotals", () => {
  it("always shows the subtotal and grand total", () => {
    const w = mountIt({ cartTotal: 100, orderTotal: 118 });
    expect(w.text()).toContain("mktMenu.subtotal");
    expect(w.text()).toContain("$100.00");
    expect(w.text()).toContain("mktMenu.total");
    expect(w.text()).toContain("$118.00");
  });

  it("shows the delivery-fee row only for delivery, with distance + free variants", () => {
    expect(mountIt({ fulfillmentType: "pickup" }).text()).not.toContain("mktMenu.deliveryFeeLabel");
    const dist = mountIt({ fulfillmentType: "delivery", deliveryFeeIsDistance: true, deliveryDistanceKm: 3, deliveryFee: 12 });
    expect(dist.text()).toContain("mktMenu.deliveryFeeLabel");
    expect(dist.text()).toContain("3 km");
    expect(dist.text()).toContain("$12.00");
    expect(mountIt({ fulfillmentType: "delivery", deliveryIsFree: true }).text()).toContain("mktMenu.freeDelivery");
  });

  it("shows flash + loyalty discount lines only when > 0", () => {
    expect(mountIt({ flashSaleDiscount: 0, loyaltyDiscount: 0 }).text()).not.toContain("mktMenu.flashDiscount");
    const w = mountIt({ flashSaleDiscount: 8, flashSalePct: 20, loyaltyDiscount: 5 });
    expect(w.text()).toContain('mktMenu.flashDiscount:{"pct":20}');
    expect(w.text()).toContain("-$8.00");
    expect(w.text()).toContain("mktMenu.loyaltyDiscount");
    expect(w.text()).toContain("-$5.00");
  });

  it("shows the ETA chip only when prepEta is present", () => {
    expect(mountIt({ prepEta: null }).text()).not.toContain("menu.etaReadyIn");
    expect(mountIt({ prepEta: { min: 20, max: 30 } }).text()).toContain('menu.etaReadyIn:{"min":20,"max":30}');
  });
});
