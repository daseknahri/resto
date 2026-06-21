/**
 * Auto-accept (Toast/Square parity) — shared client-side derivations.
 *
 * Single source of truth for reading the owner's auto-accept setting off the
 * tenant profile, used by OwnerProfile (the settings toggle) and OwnerOrders
 * (the "Auto-accepting" header chip). Default OFF: a missing or falsy flag
 * yields false so existing tenants see no change unless they explicitly opt in.
 */

export const PREP_MINUTES_DEFAULT = 20;
export const PREP_MINUTES_MIN = 5;
export const PREP_MINUTES_MAX = 180;

/**
 * True only when the owner has explicitly turned auto-accept ON. Strict
 * equality to `true` keeps the default-preserving guarantee: undefined / null /
 * false / any other value all mean "manual confirm" (today's behaviour).
 * @param {object|null|undefined} profile tenant profile object
 * @returns {boolean}
 */
export function isAutoAcceptOn(profile) {
  return profile?.auto_accept_orders === true;
}

/**
 * Clamp a prep-time value to the supported range, falling back to the default
 * for blank / non-numeric input.
 * @param {*} value
 * @returns {number}
 */
export function clampPrepMinutes(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return PREP_MINUTES_DEFAULT;
  return Math.min(PREP_MINUTES_MAX, Math.max(PREP_MINUTES_MIN, Math.round(n)));
}
