// Client preview of the promotion discount the storefront checkout applies (PlaceOrderView in
// backend/menu/views.py). The server is authoritative; these mirror it so the cart shows — and
// wallet-gates on — the total that will actually be charged.
//
// All math is in integer cents so the preview can't drift from the server's Decimal math by a
// rounding cent.

const toCents = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
};

// numerator / denominator (non-negative integers) rounded half-to-even — what Python's
// Decimal.quantize does by default (ROUND_HALF_EVEN), e.g. a 10% discount on 12.45 is 1.24.
const divRoundHalfEven = (numerator, denominator) => {
  let q = Math.floor(numerator / denominator);
  let r = numerator - q * denominator;
  // Guard the float division against an off-by-one on huge operands.
  while (r < 0) { q -= 1; r += denominator; }
  while (r >= denominator) { q += 1; r -= denominator; }
  if (2 * r > denominator) return q + 1;
  if (2 * r < denominator) return q;
  return q % 2 === 0 ? q : q + 1;
};

/**
 * The discount (currency units) a promo is worth on this cart — mirrors
 * `_compute_promo_discount(promo, food_subtotal, delivery_fee)`:
 *   percentage    → subtotal × clamp(value, 0, 100) / 100, rounded to the cent
 *   fixed         → min(subtotal, value)
 *   free_delivery → the delivery fee (pass 0 for pickup / dine-in — no fee to waive)
 */
export function promoDiscountAmount(promo, { subtotal = 0, deliveryFee = 0 } = {}) {
  if (!promo) return 0;
  const subtotalCents = Math.max(0, toCents(subtotal));
  let cents = 0;
  if (promo.promo_type === 'percentage') {
    const pctHundredths = Math.min(10000, Math.max(0, toCents(promo.discount_value)));
    cents = divRoundHalfEven(subtotalCents * pctHundredths, 10000);
  } else if (promo.promo_type === 'fixed') {
    cents = Math.min(subtotalCents, toCents(promo.discount_value));
  } else if (promo.promo_type === 'free_delivery') {
    cents = toCents(deliveryFee);
  }
  return Math.max(0, cents) / 100;
}

/** Whether the food subtotal reaches the promo's minimum (the server skips / rejects below it). */
export function promoMeetsMinimum(promo, subtotal) {
  return toCents(promo?.min_order_amount) <= toCents(subtotal);
}

/**
 * The auto-applied promo checkout will give this cart, or null — mirrors PlaceOrderView's
 * auto-apply loop: skip a promo whose minimum isn't met, keep the STRICTLY largest discount
 * (so on a tie the first one, in the server's order, wins; a 0 discount never applies).
 *
 * `promos` is GET /promo-code-check/?auto=1 — already filtered server-side to live, uncapped,
 * code-less promos in the loop's order. The loop only runs when no code was entered: a typed
 * code replaces auto-apply entirely, so callers must not use this when a code is applied.
 *
 * @returns {{ promo: object, discount: number } | null}
 */
export function pickBestAutoPromo(promos, { subtotal = 0, deliveryFee = 0 } = {}) {
  let best = null;
  let bestDiscount = 0;
  for (const promo of Array.isArray(promos) ? promos : []) {
    if (!promoMeetsMinimum(promo, subtotal)) continue;
    const discount = promoDiscountAmount(promo, { subtotal, deliveryFee });
    if (discount > bestDiscount) {
      best = promo;
      bestDiscount = discount;
    }
  }
  return best ? { promo: best, discount: bestDiscount } : null;
}
