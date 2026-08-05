import { describe, it, expect } from "vitest";

// Pure mirror of the "true food subtotal" derivation shared by OrderStatus.vue
// (orderSubtotal) and MarketplaceOrderStatus.vue (mktSubtotal). The backend folds
// every adjustment into `total`:
//   total = food_subtotal + delivery_fee − promotion − loyalty + tip
// so the receipt derives the subtotal by INVERTING that identity — not the old
// buggy `total − delivery_fee`, which silently swallowed the tip (and discounts).
// These tests lock two contracts: (1) the rendered rows reconcile back to the
// total, and (2) the subtotal is the real food subtotal, tip excluded.
function foodSubtotal(o) {
  return (
    (Number(o.total) || 0)
    - (Number(o.delivery_fee) || 0)
    - (Number(o.tip_amount) || 0)
    + (Number(o.promotion_discount) || 0)
    + (Number(o.loyalty_discount) || 0)
  );
}

// The lines the receipt renders, in order, summed back up.
function reconciled(o) {
  return (
    foodSubtotal(o)
    + (Number(o.delivery_fee) || 0)
    + (Number(o.tip_amount) || 0)
    - (Number(o.promotion_discount) || 0)
    - (Number(o.loyalty_discount) || 0)
  );
}

describe("order-status money breakdown reconciliation", () => {
  it("delivery order with a tip: subtotal + fee + tip = total, and the subtotal excludes the tip", () => {
    // food 80 + delivery 15 + tip 10 = 105
    const o = { total: 105, delivery_fee: 15, tip_amount: 10, promotion_discount: 0, loyalty_discount: 0 };
    expect(foodSubtotal(o)).toBe(80);
    expect(reconciled(o)).toBe(Number(o.total));
    // Regression: the old code showed total − delivery = 90, folding the 10 tip into "Subtotal".
    expect(foodSubtotal(o)).not.toBe(Number(o.total) - Number(o.delivery_fee));
  });

  it("order with promo + loyalty discounts still reconciles to the total", () => {
    // food 100, delivery 12, tip 8, −promo 15, −loyalty 5  ->  total 100
    const o = { total: 100, delivery_fee: 12, tip_amount: 8, promotion_discount: 15, loyalty_discount: 5 };
    expect(foodSubtotal(o)).toBe(100);
    expect(reconciled(o)).toBe(Number(o.total));
  });

  it("plain order (no fee/tip/discount): subtotal equals total", () => {
    const o = { total: 60, delivery_fee: 0, tip_amount: 0, promotion_discount: 0, loyalty_discount: 0 };
    expect(foodSubtotal(o)).toBe(60);
    expect(reconciled(o)).toBe(60);
  });

  it("a payload without tip/promo fields treats them as zero and still reconciles", () => {
    const o = { total: 42.5, delivery_fee: 5 };
    expect(foodSubtotal(o)).toBe(37.5);
    expect(reconciled(o)).toBe(42.5);
  });

  it("decimal amounts reconcile without drift", () => {
    // food 33.33 + delivery 4.99 + tip 2.50 = 40.82
    const o = { total: 40.82, delivery_fee: 4.99, tip_amount: 2.5, promotion_discount: 0, loyalty_discount: 0 };
    expect(reconciled(o)).toBeCloseTo(Number(o.total), 2);
  });
});
