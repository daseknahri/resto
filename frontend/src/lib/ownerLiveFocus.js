/**
 * ownerLiveFocus — pure, framework-free derivations shared by the owner's
 * live-ops surfaces (OwnerHome, OwnerOrders, OwnerKitchen, OwnerNextAction).
 *
 * Two concerns live here, both Wave-2 OWNER-FOCUS items:
 *
 *   1. SCHEDULED / "DUE SOON" surfacing — an advance order (status==='scheduled'
 *      or any active order carrying a future/near `scheduled_for`) should surface
 *      proactively in the live flow as its fire time approaches, instead of being
 *      invisible until it is late.
 *
 *   2. SINGLE NEXT ACTION — for a solo owner working the pass alone, compute THE
 *      one highest-priority action right now and the mutation that resolves it.
 *
 * Everything is a pure function of (orders, now) so it can be unit-tested without
 * mounting a component and reused verbatim across pages.  `now` is always passed
 * in (defaulting to Date.now()) so tests are deterministic and the components can
 * drive it off a reactive ticker.
 */

// How far ahead a scheduled order counts as "upcoming" on the live strips (~2h).
export const UPCOMING_WINDOW_MIN = 120;

// Within this many minutes of `scheduled_for` (or once it has passed) a scheduled
// order is "due soon" — the kitchen/owner should start prepping. Mirrors the
// intent of a prep window; default kept conservative until a per-restaurant
// default_prep_minutes lands (Wave 4).
export const DUE_SOON_WINDOW_MIN = 30;

// An order is "urgent" when it has sat in a live status past these thresholds.
// pending  > 15m — owner hasn't confirmed yet (customer waiting)
// confirmed > 30m — kitchen may be stuck
// preparing > 25m — running long
export const URGENT_THRESHOLDS_MIN = { pending: 15, confirmed: 30, preparing: 25 };

const _ms = (iso) => {
  if (!iso) return NaN;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? NaN : t;
};

const minutesBetween = (fromMs, toMs) => Math.round((toMs - fromMs) / 60000);

/**
 * Minutes until an order's scheduled fire time. Positive = still in the future,
 * negative = already past. NaN when the order has no scheduled_for.
 */
export function minutesUntilScheduled(order, now = Date.now()) {
  const at = _ms(order?.scheduled_for);
  if (Number.isNaN(at)) return NaN;
  return minutesBetween(now, at);
}

/** True while a scheduled order is within (or past) its due-soon window. */
export function isDueSoon(order, now = Date.now(), windowMin = DUE_SOON_WINDOW_MIN) {
  const mins = minutesUntilScheduled(order, now);
  if (Number.isNaN(mins)) return false;
  return mins <= windowMin;
}

/**
 * Upcoming / advance orders to surface in the live flow:
 *   - status === 'scheduled' (not yet released to the kitchen), OR
 *   - any non-terminal order that still carries a future scheduled_for
 * within the next `windowMin` minutes (or already due). Excludes terminal
 * (completed/cancelled) orders. Sorted by soonest fire time first.
 */
export function upcomingOrders(orders, now = Date.now(), windowMin = UPCOMING_WINDOW_MIN) {
  const terminal = new Set(["completed", "cancelled"]);
  return (orders || [])
    .filter((o) => {
      if (!o || terminal.has(o.status)) return false;
      const mins = minutesUntilScheduled(o, now);
      if (Number.isNaN(mins)) return false;
      // Within the look-ahead window, OR already due (mins <= windowMin covers both).
      return mins <= windowMin;
    })
    .sort((a, b) => _ms(a.scheduled_for) - _ms(b.scheduled_for));
}

/** Minutes an order has spent in its current live status (uses created_at). */
export function orderAgeMinutes(order, now = Date.now()) {
  const at = _ms(order?.created_at);
  if (Number.isNaN(at)) return 0;
  return Math.max(0, minutesBetween(at, now));
}

/** Mirror of the urgency rule used across the owner surfaces. */
export function isUrgentOrder(order, now = Date.now()) {
  const threshold = URGENT_THRESHOLDS_MIN[order?.status];
  if (!threshold) return false;
  return orderAgeMinutes(order, now) >= threshold;
}

// Held-course detection — a course-tagged item is held while its course is
// above the order's fired_course (default 1). Mirrors OwnerKitchen.isItemHeld.
function hasHeldCourse(order) {
  const fired = order?.fired_course ?? 1;
  return (order?.items || []).some((it) => {
    if (it.is_voided || it.is_ready) return false;
    const c = it.course ?? 0;
    return c > 0 && c > fired;
  });
}

/**
 * computeNextAction — THE single most-important thing the owner should do next.
 *
 * Priority (highest first):
 *   1. confirm  — oldest order pending past its confirm window (overdue)
 *   2. dueSoon  — a scheduled advance order now within its fire window
 *   3. handoff  — an order ready for pickup/delivery handoff
 *   4. fire     — a dine-in order with a held course ready to fire
 *   5. overdue  — an order preparing longer than expected
 *   6. soldOut  — sold-out dishes to reset
 *   7. allClear — nothing needs attention
 *
 * Returns a descriptor: { kind, order?, count?, minutes? }. The component maps
 * `kind` → label + the existing mutation. Pure: no store/i18n access.
 *
 * @param {object[]} orders
 * @param {object}   opts
 * @param {number}   opts.now           - epoch ms (default Date.now())
 * @param {number}   opts.soldOutCount  - count of 86'd dishes (from readiness)
 */
export function computeNextAction(orders, { now = Date.now(), soldOutCount = 0 } = {}) {
  const list = orders || [];
  const byOldest = (a, b) => _ms(a.created_at) - _ms(b.created_at);

  // 1. Overdue pending → confirm (only when actually past the confirm window).
  const overduePending = list
    .filter((o) => o.status === "pending" && isUrgentOrder(o, now))
    .sort(byOldest);
  if (overduePending.length) {
    const o = overduePending[0];
    return { kind: "confirm", order: o, minutes: orderAgeMinutes(o, now) };
  }

  // 2. A scheduled advance order now due → release / start.
  const due = upcomingOrders(list, now, DUE_SOON_WINDOW_MIN);
  if (due.length) {
    const o = due[0];
    return { kind: "dueSoon", order: o, minutes: minutesUntilScheduled(o, now) };
  }

  // 3. Ready → hand off (pickup/delivery/prepaid dine-in).
  const ready = list.filter((o) => o.status === "ready").sort(byOldest);
  if (ready.length) {
    return { kind: "handoff", order: ready[0] };
  }

  // 4. Dine-in order with a held course ready to fire.
  const heldFire = list
    .filter((o) => ["confirmed", "preparing"].includes(o.status) && hasHeldCourse(o))
    .sort(byOldest);
  if (heldFire.length) {
    return { kind: "fire", order: heldFire[0] };
  }

  // 5. Overdue preparing.
  const overduePreparing = list
    .filter((o) => o.status === "preparing" && isUrgentOrder(o, now))
    .sort(byOldest);
  if (overduePreparing.length) {
    const o = overduePreparing[0];
    return { kind: "overdue", order: o, minutes: orderAgeMinutes(o, now) };
  }

  // 6. Non-overdue pending still needs confirming (lower priority than overdue).
  const anyPending = list.filter((o) => o.status === "pending").sort(byOldest);
  if (anyPending.length) {
    const o = anyPending[0];
    return { kind: "confirm", order: o, minutes: orderAgeMinutes(o, now) };
  }

  // 7. Sold-out dishes to reset.
  if (soldOutCount > 0) {
    return { kind: "soldOut", count: soldOutCount };
  }

  // 8. All clear.
  return { kind: "allClear" };
}
