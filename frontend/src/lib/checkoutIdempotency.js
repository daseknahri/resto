// Idempotency for the customer checkouts (storefront /place-order/ and /marketplace/order/).
//
// The key must identify ONE cart snapshot. Reusing it for a retry of the SAME cart is the point
// (a lost response → the server replays the order instead of charging twice). But reusing it after
// the cart was edited made the server replay the order placed for the OLD cart, which the page then
// presented as the edited one (L14). So the key is tied to a fingerprint of what is being ordered,
// and any change mints a fresh key.
import { newIdempotencyKey } from './idempotency';

// JSON with object keys sorted, so the same snapshot always yields the same string.
const stableStringify = (value) => {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .filter((key) => value[key] !== undefined)
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value ?? null);
};

/**
 * What a checkout payload is ordering, for fingerprinting. Drops the key itself, and reduces
 * `redeem_points` (always "the whole balance") to whether points are redeemed — a balance refresh
 * between a lost attempt and its retry is not a different order.
 */
export function checkoutSnapshot(payload) {
  const snapshot = { ...(payload || {}) };
  delete snapshot.idempotency_key;
  snapshot.redeem_points = Boolean(snapshot.redeem_points);
  return snapshot;
}

/**
 * The `{ key, fingerprint }` to send for this snapshot: `prev` when the snapshot is unchanged
 * (retry of the same cart), else a fresh key. Callers drop it (null) after a confirmed success.
 */
export function keyForCheckoutSnapshot(prev, snapshot) {
  const fingerprint = stableStringify(snapshot);
  if (prev && prev.key && prev.fingerprint === fingerprint) return prev;
  return { key: newIdempotencyKey(), fingerprint };
}
