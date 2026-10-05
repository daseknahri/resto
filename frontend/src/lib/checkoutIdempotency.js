// Idempotency for the customer checkouts (storefront /place-order/ and /marketplace/order/).
//
// The key stands for ONE checkout attempt-chain. Rules (L14):
//   • Retry of the SAME cart → same key (a lost response → the server replays the order instead
//     of charging twice).
//   • The last attempt's outcome is UNKNOWN (no HTTP response, or a 5xx) → keep the key even if
//     the cart was edited since. That attempt may have placed — and charged — an order; a new key
//     would place and charge a SECOND one. With the old key the server replays the order that
//     exists (and if none does, the key was never stored, so the edited cart is placed under it).
//   • Every attempt with this key was DEFINITIVELY rejected (a 4xx: validation, promo_invalid,
//     items_unavailable, 402 wallet_insufficient, 403, 409…) → no order exists, so an edited cart
//     gets a fresh key: the server stores the key only on the Order row it creates inside the
//     placement transaction, so a rejected attempt leaves nothing to replay.
//   • "Unknown" is STICKY until a success: once an attempt's outcome was unknown, a later 4xx
//     on the same key proves nothing — some 4xx/409 gates (closed, ordering paused, menu
//     unpublished, throttling) answer BEFORE the server's idempotency replay check, so an order
//     from the lost attempt may still exist.
//   • Confirmed success → callers drop the state (null) so the next order mints a fresh key.
//
// A replay of an earlier, DIFFERENT cart is detected with isSameSnapshot() so the page can say
// that the earlier order went through without the later edits, instead of presenting it as the
// edited cart.
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
 * The `{ key, fingerprint, outcomeUnknown }` to send for this snapshot: `prev` when the snapshot
 * is unchanged OR the previous attempt's outcome is unknown (see the rules above); else a fresh
 * key. `fingerprint` stays the snapshot the key was FIRST sent for.
 */
export function keyForCheckoutSnapshot(prev, snapshot) {
  const fingerprint = stableStringify(snapshot);
  if (prev && prev.key && (prev.outcomeUnknown || prev.fingerprint === fingerprint)) return prev;
  return { key: newIdempotencyKey(), fingerprint, outcomeUnknown: false };
}

/** Whether `idem`'s key was minted for exactly this snapshot (vs. an earlier, edited cart). */
export function isSameSnapshot(idem, snapshot) {
  return Boolean(idem) && idem.fingerprint === stableStringify(snapshot);
}

/**
 * True when a failed request may still have placed the order: no HTTP response at all (network
 * error, timeout, lost response) or a server error (5xx — it may have failed after committing).
 */
export function isUnknownCheckoutOutcome(err) {
  const status = Number(err?.response?.status);
  return !err?.response || !Number.isFinite(status) || status >= 500;
}

/**
 * Record a failed attempt's outcome on the idempotency state (callers' catch blocks). Unknown is
 * sticky: a definitive 4xx after an unknown attempt does not prove no order exists.
 */
export function afterFailedCheckout(idem, err) {
  if (!idem) return idem;
  return { ...idem, outcomeUnknown: Boolean(idem.outcomeUnknown) || isUnknownCheckoutOutcome(err) };
}
