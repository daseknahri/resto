// Client projection of the loyalty points an order credits — shared by the storefront cart and
// the marketplace checkout. Mirrors what BOTH server checkouts grant (PlaceOrderView and
// MarketplacePlaceOrderView):
//
//   floor(food_subtotal × points_per_unit × tier multiplier)   — menu/views._loyalty_points_earned
//   + first_order_bonus_points when the customer has no non-cancelled order there yet
//
// The base is the FOOD subtotal (no delivery fee, tip or discounts). Integer math (cents ×
// points-per-unit × multiplier-hundredths) so the floor never drops or gains a point to float
// error, exactly like the server's Decimal math.

const toHundredths = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
};

const toInt = (value) => {
  const n = Math.trunc(Number(value));
  return Number.isFinite(n) ? n : 0;
};

/**
 * The tier multiplier for a customer's lifetime points, in hundredths (150 = ×1.50). Mirrors the
 * server: Gold at ≥ gold threshold, else Silver at ≥ silver threshold, else ×1; unset/zero
 * config values fall back to the model defaults (500 / 2000, ×1.50 / ×2.00), like its `or`.
 */
export function loyaltyTierMultiplierHundredths(cfg, lifetimePoints) {
  if (!cfg?.tier_enabled) return 100;
  const lifetime = toInt(lifetimePoints);
  const goldThreshold = toInt(cfg.tier_gold_threshold) || 2000;
  const silverThreshold = toInt(cfg.tier_silver_threshold) || 500;
  if (lifetime >= goldThreshold) return toHundredths(cfg.tier_gold_multiplier) || 200;
  if (lifetime >= silverThreshold) return toHundredths(cfg.tier_silver_multiplier) || 150;
  return 100;
}

/**
 * Points this order would credit to the customer. 0 when signed out (only a signed-in customer
 * earns) or loyalty is off.
 *
 * @param {object} args
 * @param {object|null} args.cfg  loyalty config (`/customer/loyalty/config/` or the marketplace
 *   menu's `loyalty`), incl. `first_order_bonus_eligible` for the signed-in customer.
 * @param {number|string} args.foodSubtotal  items subtotal, before fees/discounts/tip.
 * @param {number|string} [args.lifetimePoints]  the customer's lifetime points (tier).
 * @param {boolean} [args.signedIn]
 */
export function projectLoyaltyEarn({ cfg, foodSubtotal, lifetimePoints = 0, signedIn = true }) {
  if (!signedIn || !cfg?.enabled) return 0;
  const cents = Math.round((Number(foodSubtotal) || 0) * 100);
  const pointsPerUnit = toInt(cfg.points_per_unit);
  const scaled = cents * pointsPerUnit * loyaltyTierMultiplierHundredths(cfg, lifetimePoints);
  const earned = scaled > 0 ? (scaled - (scaled % 10000)) / 10000 : 0;
  const bonus = cfg.first_order_bonus_eligible === true
    ? Math.max(0, toInt(cfg.first_order_bonus_points))
    : 0;
  return earned + bonus;
}
