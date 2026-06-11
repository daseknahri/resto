/**
 * Single source of truth for order-status chip and dot colors.
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
