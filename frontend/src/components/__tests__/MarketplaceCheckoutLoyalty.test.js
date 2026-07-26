/**
 * Unit tests for MarketplaceCheckoutLoyalty — the loyalty redeem toggle + earn
 * projection of the Marketplace checkout drawer (RISK FE-2). useLoyalty is a
 * two-way model; the redeem label + earn line are independently gated.
 */
import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";

vi.mock("../../composables/useI18n", () => ({
  useI18n: () => ({ t: (k, p) => (p ? `${k}:${JSON.stringify(p)}` : k) }),
}));

import MarketplaceCheckoutLoyalty from "../MarketplaceCheckoutLoyalty.vue";

const mountIt = (props = {}) =>
  mount(MarketplaceCheckoutLoyalty, {
    props: {
      useLoyalty: false, available: true, points: 120, discount: 15,
      earnEnabled: false, earnProjection: 0, fmtPrice: (n) => `$${Number(n).toFixed(2)}`, ...props,
    },
  });

describe("MarketplaceCheckoutLoyalty", () => {
  it("renders the redeem label with the point balance when available", () => {
    const w = mountIt();
    expect(w.find("label").exists()).toBe(true);
    expect(w.text()).toContain('mktMenu.loyaltyRedeem:{"points":120}');
  });

  it("hides the redeem label when redemption is unavailable", () => {
    expect(mountIt({ available: false }).find("label").exists()).toBe(false);
  });

  it("shows the discount only when redeeming and discount > 0", () => {
    expect(mountIt({ useLoyalty: false, discount: 15 }).text()).not.toContain("-$15.00");
    expect(mountIt({ useLoyalty: true, discount: 15 }).text()).toContain("-$15.00");
  });

  it("emits update:useLoyalty when the checkbox is toggled", async () => {
    const w = mountIt();
    await w.find('input[type="checkbox"]').setValue(true);
    expect(w.emitted("update:useLoyalty")[0]).toEqual([true]);
  });

  it("shows the earn projection only when earning is enabled and > 0", () => {
    expect(mountIt({ earnEnabled: true, earnProjection: 8 }).text()).toContain('mktMenu.loyaltyEarnProjection:{"points":8}');
    expect(mountIt({ earnEnabled: true, earnProjection: 0 }).text()).not.toContain("loyaltyEarnProjection");
    expect(mountIt({ earnEnabled: false, earnProjection: 8 }).text()).not.toContain("loyaltyEarnProjection");
  });
});
