/**
 * lib/promoPreview — the cart's preview of the promotion discount PlaceOrderView applies
 * (backend menu/views.py: _compute_promo_discount + the auto-apply loop). M8: the cart only
 * previewed a typed code, so with an auto promo live it quoted — and wallet-gated on — more
 * than it charged.
 */
import { describe, it, expect } from "vitest";
import { pickBestAutoPromo, promoDiscountAmount, promoMeetsMinimum } from "../promoPreview";

const pct = (value, extra = {}) => ({ name: `${value}%`, promo_type: "percentage", discount_value: String(value), min_order_amount: "0.00", ...extra });
const fixed = (value, extra = {}) => ({ name: `-${value}`, promo_type: "fixed", discount_value: String(value), min_order_amount: "0.00", ...extra });
const freeDelivery = (extra = {}) => ({ name: "Free delivery", promo_type: "free_delivery", discount_value: "0.00", min_order_amount: "0.00", ...extra });

describe("promoDiscountAmount (= _compute_promo_discount)", () => {
  it("percentage: subtotal × pct / 100, rounded half-to-even like Decimal.quantize", () => {
    expect(promoDiscountAmount(pct(10), { subtotal: 100 })).toBe(10);
    // 1.245 → 1.24 and 1.235 → 1.24 (half-even), 1.255 → 1.26 — never Math.round's 1.25/1.24/1.26 drift.
    expect(promoDiscountAmount(pct(10), { subtotal: 12.45 })).toBe(1.24);
    expect(promoDiscountAmount(pct(10), { subtotal: 12.35 })).toBe(1.24);
    expect(promoDiscountAmount(pct(10), { subtotal: 12.55 })).toBe(1.26);
    // A float-noisy cart sum (0.1 + 0.2) is read as its cents.
    expect(promoDiscountAmount(pct(50), { subtotal: 0.1 + 0.2 })).toBe(0.15);
  });

  it("percentage is clamped to 0..100", () => {
    expect(promoDiscountAmount(pct(150), { subtotal: 40 })).toBe(40);
    expect(promoDiscountAmount(pct(-5), { subtotal: 40 })).toBe(0);
  });

  it("fixed: min(subtotal, value)", () => {
    expect(promoDiscountAmount(fixed(15), { subtotal: 100 })).toBe(15);
    expect(promoDiscountAmount(fixed(15), { subtotal: 9.5 })).toBe(9.5);
  });

  it("free_delivery is worth exactly the delivery fee passed in (0 for pickup / dine-in)", () => {
    expect(promoDiscountAmount(freeDelivery(), { subtotal: 100, deliveryFee: 17.5 })).toBe(17.5);
    expect(promoDiscountAmount(freeDelivery(), { subtotal: 100, deliveryFee: 0 })).toBe(0);
  });

  it("unknown type / no promo → 0", () => {
    expect(promoDiscountAmount(null, { subtotal: 100 })).toBe(0);
    expect(promoDiscountAmount({ promo_type: "mystery", discount_value: "5" }, { subtotal: 100 })).toBe(0);
  });
});

describe("promoMeetsMinimum", () => {
  it("compares the food subtotal with min_order_amount (inclusive)", () => {
    expect(promoMeetsMinimum({ min_order_amount: "50.00" }, 50)).toBe(true);
    expect(promoMeetsMinimum({ min_order_amount: "50.00" }, 49.99)).toBe(false);
    expect(promoMeetsMinimum({ min_order_amount: "0.00" }, 0)).toBe(true);
  });
});

describe("pickBestAutoPromo (= PlaceOrderView's auto-apply loop)", () => {
  it("takes the largest discount among promos whose minimum is met", () => {
    const promos = [pct(10), fixed(15, { min_order_amount: "200.00" }), fixed(12)];
    const best = pickBestAutoPromo(promos, { subtotal: 100 });
    expect(best.promo.name).toBe("-12");
    expect(best.discount).toBe(12);
  });

  it("keeps the FIRST promo on a tie (strict >, server order)", () => {
    const first = fixed(10, { name: "Newest" });
    const second = pct(10, { name: "Older" });
    expect(pickBestAutoPromo([first, second], { subtotal: 100 }).promo.name).toBe("Newest");
  });

  it("never applies a zero discount — e.g. free delivery on a pickup order", () => {
    expect(pickBestAutoPromo([freeDelivery()], { subtotal: 100, deliveryFee: 0 })).toBeNull();
    expect(pickBestAutoPromo([freeDelivery()], { subtotal: 100, deliveryFee: 20 }).discount).toBe(20);
  });

  it("is null for no / malformed promo lists", () => {
    expect(pickBestAutoPromo([], { subtotal: 100 })).toBeNull();
    expect(pickBestAutoPromo(undefined, { subtotal: 100 })).toBeNull();
  });
});
