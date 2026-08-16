// Pure resolution of re-order items against a live menu, shared-shape helper for the
// marketplace reorder path (MarketplaceMenuPage). Mirrors the tenant reorder spine's
// contract: drop items that are no longer on the menu OR currently sold out
// (`is_available === false`, matching the `unavailableSlugs` checkout guard), carry each
// line's selected options + per-item note, revalidate those options against the live
// dish (dropping any that no longer exist, like the backend `stale_options` path), and
// re-price each surviving line to the live effective base (happy-hour-aware) plus the
// live price_delta of the options that survived. Returns the seeded cart lines plus
// flags so the caller can toast when anything changed.
//
// Why it matters: the marketplace cart lives on a different origin than the tenant
// storefront cart, so it can't reuse the Pinia `useReorder` action (which delegates
// option revalidation to POST /reorder-resolve/). Before this helper carried options,
// marketplace reorder seeded every line with `options: []` at the bare base price — so a
// dish in a required option group hard-failed checkout (`option_selection_invalid`) with
// no way to recover, and a dish with paid extras was silently re-ordered without them
// (wrong order sent to the kitchen + undercharge). The option ids live in the snapshot;
// this was pure client-side data loss, so the fix is to preserve + revalidate them here.
//
// Kept pure (no Vue/DOM/state) so it is unit-testable and can't drift from the guard.

/**
 * @typedef {{ id: (number|string), name?: string, price_delta?: (number|string) }} OptionSnapshot
 * @param {Array<{
 *   slug?: string, name?: string, price?: (number|string), qty?: (number|string),
 *   note?: string, options?: Array<OptionSnapshot>
 * }>} items
 *   Re-order snapshot items (order `items_snapshot` / status items via nav state). `price`
 *   is the past unit price (already includes the original options' deltas); `options`
 *   carries the selected option snapshots.
 * @param {Map<string, {
 *   slug: string, name?: string, price?: (number|string), is_available?: boolean,
 *   effective_price?: (number|string),
 *   happy_hour?: ({ ends_at?: (string|null), starts_at?: (string|null) }|null),
 *   option_groups?: Array<{ options?: Array<OptionSnapshot> }>
 * }>} dishMap
 *   The current menu keyed by dish slug (full live dish objects, incl. `option_groups`).
 * @returns {{ cart: Array<object>, priceChanged: boolean, dropped: boolean }}
 */
export function resolveMarketplaceReorderItems(items, dishMap) {
  const cart = [];
  let priceChanged = false;
  let dropped = false;
  if (!Array.isArray(items) || !dishMap) return { cart, priceChanged, dropped };

  for (const item of items) {
    if (!item || !item.slug) continue;
    const live = dishMap.get(item.slug);
    // Drop unknown or sold-out dishes. `=== false` (not `!is_available`) matches the
    // unavailableSlugs checkout guard exactly, so reorder drops precisely what checkout
    // would block — and a dish with an absent `is_available` is treated as available.
    if (!live || live.is_available === false) {
      dropped = true;
      continue;
    }

    // Revalidate the snapshot's options against the live dish: keep only options that
    // still exist on the current menu (dropping stale ones, mirroring the backend
    // `stale_options` behaviour), using the LIVE name + price_delta so the seeded line —
    // and the `option_ids` it later posts at checkout — always match today's menu.
    const liveOptions = new Map();
    for (const grp of live.option_groups || []) {
      for (const opt of grp.options || []) {
        if (opt && opt.id != null) liveOptions.set(opt.id, opt);
      }
    }
    const snapOptions = Array.isArray(item.options) ? item.options : [];
    const keptOptions = [];
    for (const snap of snapOptions) {
      if (!snap || snap.id == null) continue;
      const liveOpt = liveOptions.get(snap.id);
      if (liveOpt) {
        keptOptions.push({ id: liveOpt.id, name: liveOpt.name, price_delta: liveOpt.price_delta });
      }
    }
    // A selected option that has since left the menu is a real change to the line.
    const snapOptionCount = snapOptions.filter((o) => o && o.id != null).length;
    if (keptOptions.length !== snapOptionCount) priceChanged = true;

    // Live effective base is happy-hour-aware, matching how the cart builds a fresh line
    // (MarketplaceMenuPage optionPanelUnitPrice / confirmOptionSelection). Option deltas
    // are never discounted.
    const base = Number(live.price) || 0;
    const eff = Number(live.effective_price);
    const effectiveBase = (live.happy_hour && Number.isFinite(eff) && eff < base) ? eff : base;
    const optionsTotal = keptOptions.reduce((sum, o) => sum + (Number(o.price_delta) || 0), 0);
    const unitPrice = effectiveBase + optionsTotal;

    // `item.price` is the past order's unit price (already includes the original options'
    // deltas), so comparing it to the freshly-computed unit price flags any drift.
    const snapshotUnit = Number(item.price) || 0;
    if (snapshotUnit !== unitPrice) priceChanged = true;

    cart.push({
      slug: live.slug,
      name: live.name || item.name || live.slug,
      price: base,
      unitPrice,
      qty: Math.max(1, Math.floor(Number(item.qty) || 1)),
      options: keptOptions,
      note: typeof item.note === 'string' ? item.note : '',
      happy_hour_ends_at: live.happy_hour?.ends_at ?? null,
      happy_hour_starts_at: live.happy_hour?.starts_at ?? null,
    });
  }
  return { cart, priceChanged, dropped };
}
