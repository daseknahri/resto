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

// R6-16: unconfirmed-order SLA + auto-cancel (OwnerProfile "Unconfirmed
// orders"). The SLA is when the owner gets reminded; auto-cancel (0 = never)
// only ever fires on an order that was already escalated, and must exceed the
// SLA — the backend enforces the same rule, this mirrors it client-side.
export const PENDING_SLA_DEFAULT = 10;
export const PENDING_SLA_MIN = 1;
export const PENDING_SLA_MAX = 120;
export const PENDING_AUTO_CANCEL_DEFAULT = 0;
export const PENDING_AUTO_CANCEL_MIN = 0;
export const PENDING_AUTO_CANCEL_MAX = 480;

/**
 * Clamp an escalation-SLA value to the supported range, falling back to the
 * platform default (10 min) for blank / non-numeric input.
 * @param {*} value
 * @returns {number}
 */
export function clampPendingSlaMinutes(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return PENDING_SLA_DEFAULT;
  return Math.min(PENDING_SLA_MAX, Math.max(PENDING_SLA_MIN, Math.round(n)));
}

/**
 * Clamp an auto-cancel value to the supported range, falling back to 0
 * (never) for blank / non-numeric input.
 * @param {*} value
 * @returns {number}
 */
export function clampPendingAutoCancelMinutes(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return PENDING_AUTO_CANCEL_DEFAULT;
  return Math.min(
    PENDING_AUTO_CANCEL_MAX,
    Math.max(PENDING_AUTO_CANCEL_MIN, Math.round(n)),
  );
}

/**
 * True when an auto-cancel value is legal against an SLA: 0 (never), or
 * strictly more than the SLA.
 * @param {*} autoCancelMinutes
 * @param {*} slaMinutes
 * @returns {boolean}
 */
export function isAutoCancelValid(autoCancelMinutes, slaMinutes) {
  const cancel = clampPendingAutoCancelMinutes(autoCancelMinutes);
  return cancel === 0 || cancel > clampPendingSlaMinutes(slaMinutes);
}
