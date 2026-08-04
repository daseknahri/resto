/**
 * Unit tests for MarketplaceCheckoutWarnings — the pre-submit warning banners of the
 * Marketplace checkout drawer, a DISPLAY-ONLY fragment (RISK FE-2). Each banner is
 * independently gated by parent-derived conditions.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import MarketplaceCheckoutWarnings from "../MarketplaceCheckoutWarnings.vue";

const base = {
  fulfillmentType: "pickup", deliveryMinGap: 0, isClosed: false,
  isAuthenticated: true, fmtPrice: (n) => `$${Number(n).toFixed(2)}`,
};
const mountIt = (props = {}) => mount(MarketplaceCheckoutWarnings, { props: { ...base, ...props } });

describe("MarketplaceCheckoutWarnings", () => {
  it("renders nothing when no warning condition holds", () => {
    expect(mountIt().text()).toBe("");
  });

  it("shows the minimum-order banner only for delivery with a gap", () => {
    expect(mountIt({ fulfillmentType: "pickup", deliveryMinGap: 10 }).text()).not.toContain("mktMenu.deliveryMinAddMore");
    expect(mountIt({ fulfillmentType: "delivery", deliveryMinGap: 10 }).text()).toContain('mktMenu.deliveryMinAddMore:{"amount":"$10.00"}');
  });

  it("shows the closed banner when isClosed", () => {
    expect(mountIt({ isClosed: true }).text()).toContain("mktMenu.restaurantClosed");
    expect(mountIt({ isClosed: false }).text()).not.toContain("mktMenu.restaurantClosed");
  });

  it("shows the guest banner only for a signed-out delivery order", () => {
    expect(mountIt({ fulfillmentType: "delivery", isAuthenticated: false }).text()).toContain("mktMenu.authRequired");
    expect(mountIt({ fulfillmentType: "delivery", isAuthenticated: true }).text()).not.toContain("mktMenu.authRequired");
    expect(mountIt({ fulfillmentType: "pickup", isAuthenticated: false }).text()).not.toContain("mktMenu.authRequired");
  });

  it("emits signIn when the guest banner's Sign in button is tapped", async () => {
    const w = mountIt({ fulfillmentType: "delivery", isAuthenticated: false });
    await w.find('[role="status"] button').trigger("click");
    expect(w.emitted("signIn")).toHaveLength(1);
  });

  it("can show multiple banners at once", () => {
    const w = mountIt({ fulfillmentType: "delivery", deliveryMinGap: 5, isClosed: true, isAuthenticated: false });
    expect(w.findAll('[role="alert"], [role="status"]')).toHaveLength(3);
  });
});
