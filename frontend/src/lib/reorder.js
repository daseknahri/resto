// Pure resolution of re-order items against a live menu, shared-shape helper for the
// marketplace reorder path (MarketplaceMenuPage). Mirrors the tenant reorder spine's
// contract: drop items that are no longer on the menu OR currently sold out
// (`is_available === false`, matching the `unavailableSlugs` checkout guard), and
// re-price surviving items to the live price. Returns the seeded cart lines plus flags
// so the caller can toast when anything changed.
//
// Why it matters: the marketplace cart lives on a different origin than the tenant
// storefront cart, so it can't reuse the Pinia `useReorder` action. Before this helper,
// marketplace reorder checked only "is the dish still on the menu" — a sold-out dish was
// seeded into the cart and then blocked checkout via `unavailableSlugs` until the user
// removed it by hand, instead of being cleanly dropped like every other reorder path.
//
// Kept pure (no Vue/DOM/state) so it is unit-testable and can't drift from the guard.

/**
 * @param {Array<{slug?: string, name?: string, price?: number|string, qty?: number|string}>} items
 *   Re-order snapshot items (from CustomerOrderRef via nav state).
 * @param {Map<string, {slug: string, name?: string, price?: number|string, is_available?: boolean}>} dishMap
 *   The current menu keyed by dish slug.
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
    const snapshotPrice = Number(item.price) || 0;
    const livePrice = Number(live.price) || 0;
    if (snapshotPrice !== livePrice) priceChanged = true;
    cart.push({
      slug: live.slug,
      name: live.name || item.name || live.slug,
      price: livePrice,
      unitPrice: livePrice,
      qty: Math.max(1, Math.floor(Number(item.qty) || 1)),
      options: [],
    });
  }
  return { cart, priceChanged, dropped };
}
