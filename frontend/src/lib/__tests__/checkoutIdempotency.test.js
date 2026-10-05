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

import { checkoutSnapshot, keyForCheckoutSnapshot } from "../checkoutIdempotency";

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

  it("mints a new key as soon as what is being ordered changes", () => {
    const first = keyForCheckoutSnapshot(null, checkoutSnapshot(payload()));
    const editedQty = keyForCheckoutSnapshot(first, checkoutSnapshot(payload({ items: [{ slug: "burger", qty: 2 }] })));
    expect(editedQty.key).not.toBe(first.key);
    const editedTip = keyForCheckoutSnapshot(editedQty, checkoutSnapshot(payload({ items: [{ slug: "burger", qty: 2 }], tip_amount: 5 })));
    expect(editedTip.key).not.toBe(editedQty.key);
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
