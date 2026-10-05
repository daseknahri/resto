import { getDateTimeFormat } from "./intlFormatters";

/**
 * Single source of truth for order-status chip and dot colors (staff surfaces) and
 * for the customer-facing status labels / "active" set (below).
 * Only literal Tailwind class strings (purge-safe — no dynamic concatenation).
 *
 * chip: full class string for rounded-full pill badges
 * dot:  class string for a small colored status dot
 */
export const STATUS_META = {
  pending: {
    chip: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    dot:  "bg-amber-400",
  },
  confirmed: {
    chip: "border-sky-500/40 bg-sky-500/10 text-sky-300",
    dot:  "bg-sky-400",
  },
  preparing: {
    chip: "border-violet-500/40 bg-violet-500/10 text-violet-300",
    dot:  "bg-violet-400",
  },
  ready: {
    chip: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    dot:  "bg-emerald-400",
  },
  out_for_delivery: {
    chip: "border-indigo-500/40 bg-indigo-500/10 text-indigo-300",
    dot:  "bg-indigo-400",
  },
  completed: {
    chip: "border-emerald-600/40 bg-emerald-600/10 text-emerald-400",
    dot:  "bg-emerald-500",
  },
  cancelled: {
    chip: "border-red-500/40 bg-red-500/10 text-red-300",
    dot:  "bg-red-400",
  },
  scheduled: {
    chip: "border-slate-500/40 bg-slate-700/40 text-slate-300",
    dot:  "bg-slate-400",
  },
};

/** Convenience getter — falls back to a neutral slate chip when status is unknown. */
export function chipClass(status) {
  return (STATUS_META[status] ?? STATUS_META.scheduled).chip;
}

export function dotClass(status) {
  return (STATUS_META[status] ?? STATUS_META.scheduled).dot;
}

// ── Customer-facing status labels ────────────────────────────────────────────
// Single source for the customer account page and its Orders tab. Each used to keep
// its own copy of this map, and both silently lacked `scheduled`, so a prepaid
// advance order was badged "Pending".

/** Order status → i18n key for the customer's own order lists. */
export const CUSTOMER_STATUS_I18N = {
  scheduled: "orderStatus.statusScheduled",
  pending: "orderStatus.statusPending",
  confirmed: "orderStatus.statusConfirmed",
  preparing: "orderStatus.statusPreparing",
  ready: "orderStatus.statusReady",
  out_for_delivery: "orderStatus.stepOutForDelivery",
  completed: "orderStatus.statusCompleted",
  cancelled: "orderStatus.statusCancelled",
};

/** i18n key for a customer-facing order status (unknown → "Pending", as before). */
export function customerStatusKey(status) {
  return CUSTOMER_STATUS_I18N[status] || "orderStatus.statusPending";
}

/**
 * Statuses a customer sees as live / still in progress (live-order banner, pulsing
 * dot). `scheduled` belongs here: a prepaid advance order is a live commitment the
 * customer needs a way back to, not history.
 */
export const CUSTOMER_ACTIVE_STATUSES = new Set([
  "scheduled", "pending", "confirmed", "preparing", "ready", "out_for_delivery",
]);

const SCHEDULED_DUE_OPTIONS = {
  weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
};

/** "Tue 7 Oct, 19:30"-style due time for a scheduled order ('' when absent/invalid). */
export function formatScheduledDue(locale, iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  try {
    return getDateTimeFormat(locale, SCHEDULED_DUE_OPTIONS).format(date);
  } catch {
    return date.toLocaleString();
  }
}
