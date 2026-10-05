/**
 * lib/loyaltyEarn — the checkout's "you'll earn N points" must equal what the server credits
 * (L6): floor(food_subtotal × points_per_unit × tier multiplier) in exact Decimal math
 * (menu/views._loyalty_points_earned) + the first-order bonus. The old projections ignored the
 * tier multiplier and the bonus, and the marketplace one also counted the delivery fee.
 */
import { describe, it, expect } from "vitest";
import { loyaltyTierMultiplierHundredths, projectLoyaltyEarn } from "../loyaltyEarn";

const cfg = (over = {}) => ({
  enabled: true,
  points_per_unit: 10,
  tier_enabled: false,
  tier_silver_threshold: 500,
  tier_gold_threshold: 2000,
  tier_silver_multiplier: "1.50",
  tier_gold_multiplier: "2.00",
  first_order_bonus_points: 0,
  first_order_bonus_eligible: false,
  ...over,
});

describe("projectLoyaltyEarn — base formula (same vectors as the backend tests)", () => {
  it("floors exactly, without float error", () => {
    // 0.29 × 100 is 28.999… in floats; the server's Decimal math gives 29.
    expect(projectLoyaltyEarn({ cfg: cfg({ points_per_unit: 100 }), foodSubtotal: 0.29 })).toBe(29);
    expect(projectLoyaltyEarn({ cfg: cfg(), foodSubtotal: "12.34" })).toBe(123);
    expect(projectLoyaltyEarn({ cfg: cfg(), foodSubtotal: 20 })).toBe(200);
  });

  it("earns nothing on a zero / negative subtotal, when disabled, or when signed out", () => {
    expect(projectLoyaltyEarn({ cfg: cfg(), foodSubtotal: 0 })).toBe(0);
    expect(projectLoyaltyEarn({ cfg: cfg(), foodSubtotal: -5 })).toBe(0);
    expect(projectLoyaltyEarn({ cfg: cfg({ enabled: false }), foodSubtotal: 50 })).toBe(0);
    expect(projectLoyaltyEarn({ cfg: null, foodSubtotal: 50 })).toBe(0);
    expect(projectLoyaltyEarn({ cfg: cfg(), foodSubtotal: 50, signedIn: false })).toBe(0);
  });
});

describe("projectLoyaltyEarn — tier multiplier", () => {
  const tiered = cfg({ tier_enabled: true });

  it("applies Silver / Gold by lifetime points (thresholds inclusive)", () => {
    expect(projectLoyaltyEarn({ cfg: tiered, foodSubtotal: "12.34", lifetimePoints: 499 })).toBe(123);
    expect(projectLoyaltyEarn({ cfg: tiered, foodSubtotal: "12.34", lifetimePoints: 500 })).toBe(185);
    expect(projectLoyaltyEarn({ cfg: tiered, foodSubtotal: "12.34", lifetimePoints: 2000 })).toBe(246);
    expect(projectLoyaltyEarn({ cfg: tiered, foodSubtotal: "9.99", lifetimePoints: 700 })).toBe(149);
  });

  it("ignores lifetime points while tiers are off", () => {
    expect(projectLoyaltyEarn({ cfg: cfg(), foodSubtotal: 10, lifetimePoints: 5000 })).toBe(100);
  });

  it("falls back to the model defaults for unset config, like the server's `or`", () => {
    const sparse = { tier_enabled: true, tier_silver_threshold: 0, tier_gold_threshold: 0, tier_silver_multiplier: "0", tier_gold_multiplier: null };
    expect(loyaltyTierMultiplierHundredths(sparse, 499)).toBe(100);
    expect(loyaltyTierMultiplierHundredths(sparse, 500)).toBe(150);
    expect(loyaltyTierMultiplierHundredths(sparse, 2000)).toBe(200);
  });
});

describe("projectLoyaltyEarn — first-order bonus", () => {
  it("adds the bonus only when the customer is eligible", () => {
    const withBonus = cfg({ first_order_bonus_points: 50 });
    expect(projectLoyaltyEarn({ cfg: { ...withBonus, first_order_bonus_eligible: true }, foodSubtotal: 10 })).toBe(150);
    expect(projectLoyaltyEarn({ cfg: withBonus, foodSubtotal: 10 })).toBe(100);
  });

  it("is granted even when the base earns nothing (points_per_unit 0)", () => {
    expect(projectLoyaltyEarn({
      cfg: cfg({ points_per_unit: 0, first_order_bonus_points: 25, first_order_bonus_eligible: true }),
      foodSubtotal: 10,
    })).toBe(25);
  });
});
