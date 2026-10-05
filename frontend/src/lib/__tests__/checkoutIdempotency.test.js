/**
 * lib/checkoutIdempotency — L14: a checkout idempotency key identifies ONE cart snapshot.
 * Reusing it after the cart was edited made the server replay the OLD cart's order, which the
 * page then showed as if the edited cart had been placed.
 */
import { describe, it, expect, vi } from "vitest";

vi.mock("../idempotency", () => {
  let n = 0;
  return { newIdempotencyKey: () => `key-${++n}` };
});

import {
  afterFailedCheckout,
  checkoutSnapshot,
  isSameSnapshot,
  isUnknownCheckoutOutcome,
  keyForCheckoutSnapshot,
} from "../checkoutIdempotency";

const networkError = () => new Error("Network Error"); // no response — outcome unknown
const httpError = (status, code = "x") => ({ response: { status, data: { code } } });

const payload = (over = {}) => ({
  items: [{ slug: "burger", qty: 1 }],
  fulfillment_type: "pickup",
  use_wallet: true,
  ...over,
});

describe("keyForCheckoutSnapshot", () => {
  it("reuses the key for a retry of the same cart", () => {
    const first = keyForCheckoutSnapshot(null, checkoutSnapshot(payload()));
    const retry = keyForCheckoutSnapshot(first, checkoutSnapshot(payload()));
    expect(retry.key).toBe(first.key);
  });

  it("after a DEFINITIVE 4xx rejection, an edited cart gets a new key (no order exists)", () => {
    const first = afterFailedCheckout(keyForCheckoutSnapshot(null, checkoutSnapshot(payload())), httpError(400, "promo_invalid"));
    const editedQty = keyForCheckoutSnapshot(first, checkoutSnapshot(payload({ items: [{ slug: "burger", qty: 2 }] })));
    expect(editedQty.key).not.toBe(first.key);
    const rejected = afterFailedCheckout(editedQty, httpError(402, "wallet_insufficient"));
    const editedTip = keyForCheckoutSnapshot(rejected, checkoutSnapshot(payload({ items: [{ slug: "burger", qty: 2 }], tip_amount: 5 })));
    expect(editedTip.key).not.toBe(editedQty.key);
  });

  it("after an UNKNOWN outcome (no response), an edited cart KEEPS the key — the lost attempt may have charged", () => {
    const first = afterFailedCheckout(keyForCheckoutSnapshot(null, checkoutSnapshot(payload())), networkError());
    const edited = checkoutSnapshot(payload({ items: [{ slug: "burger", qty: 2 }] }));
    const retry = keyForCheckoutSnapshot(first, edited);
    expect(retry.key).toBe(first.key);
    // …and the caller can tell a replay would be of the EARLIER cart.
    expect(isSameSnapshot(retry, edited)).toBe(false);
    expect(isSameSnapshot(retry, checkoutSnapshot(payload()))).toBe(true);
  });

  it("treats a 5xx as unknown too (the server may have failed after committing)", () => {
    const first = afterFailedCheckout(keyForCheckoutSnapshot(null, checkoutSnapshot(payload())), httpError(503));
    expect(keyForCheckoutSnapshot(first, checkoutSnapshot(payload({ tip_amount: 3 }))).key).toBe(first.key);
  });

  it("unknown is sticky: a later 4xx on the same key doesn't release it", () => {
    // Some 409/403 gates (closed, ordering paused…) answer before the server's replay check,
    // so they don't prove the lost attempt placed nothing.
    let idem = afterFailedCheckout(keyForCheckoutSnapshot(null, checkoutSnapshot(payload())), networkError());
    idem = afterFailedCheckout(keyForCheckoutSnapshot(idem, checkoutSnapshot(payload())), httpError(409, "ordering_paused"));
    expect(keyForCheckoutSnapshot(idem, checkoutSnapshot(payload({ tip_amount: 3 }))).key).toBe(idem.key);
  });

  it("classifies outcomes", () => {
    expect(isUnknownCheckoutOutcome(networkError())).toBe(true);
    expect(isUnknownCheckoutOutcome(httpError(500))).toBe(true);
    expect(isUnknownCheckoutOutcome(httpError(400))).toBe(false);
    expect(isUnknownCheckoutOutcome(httpError(402))).toBe(false);
    expect(isUnknownCheckoutOutcome(httpError(409))).toBe(false);
  });

  it("ignores key order, the idempotency_key itself and a refreshed points balance", () => {
    const first = keyForCheckoutSnapshot(null, checkoutSnapshot(payload({ redeem_points: 120 })));
    const sameIntent = keyForCheckoutSnapshot(first, checkoutSnapshot({
      use_wallet: true,
      fulfillment_type: "pickup",
      items: [{ qty: 1, slug: "burger" }],
      redeem_points: 80, // balance re-synced between attempts — still "redeem my points"
      idempotency_key: "whatever",
    }));
    expect(sameIntent.key).toBe(first.key);
    // …but turning redemption off IS a different order.
    const noRedeem = keyForCheckoutSnapshot(first, checkoutSnapshot(payload()));
    expect(noRedeem.key).not.toBe(first.key);
  });
});
