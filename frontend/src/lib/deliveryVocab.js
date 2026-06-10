/**
 * deliveryVocab.js
 *
 * Pure helper — maps (businessType, variant) to the correct i18n key from the
 * `deliveryVocab` block so every surface uses identical branching logic.
 *
 * @param {string|null|undefined} businessType - value from the payload's
 *   business_type field ("restaurant" | "pharmacy" | "retail" | "grocery" |
 *   "bakery" | … future).  Missing/null/empty falls back to the restaurant key.
 * @param {'at'|'preparing'|'collect'} variant
 *   - 'at'       → "At the restaurant / store / pharmacy"  (tracker status label)
 *   - 'preparing' → "The kitchen / store / pharmacy is preparing your order"
 *   - 'collect'  → "Collect at the restaurant / store / pharmacy"
 * @returns {string} Fully-qualified i18n key, e.g. "deliveryVocab.atPickupStore"
 */
export function pickupLabelKey(businessType, variant) {
  const bt = (businessType || '').toLowerCase();
  const isPharmacy = bt === 'pharmacy';
  const isStore = bt === 'retail' || bt === 'grocery' || bt === 'bakery';
  // 'cafe' (and anything unknown / missing on old payloads) deliberately falls
  // through to the restaurant wording — cafés are kitchen-prep food businesses.

  if (variant === 'at') {
    if (isPharmacy) return 'deliveryVocab.atPickupPharmacy';
    if (isStore)    return 'deliveryVocab.atPickupStore';
    return 'deliveryVocab.atPickupRestaurant';
  }
  if (variant === 'preparing') {
    if (isPharmacy) return 'deliveryVocab.preparingPharmacy';
    if (isStore)    return 'deliveryVocab.preparingStore';
    return 'deliveryVocab.preparingRestaurant';
  }
  if (variant === 'collect') {
    if (isPharmacy) return 'deliveryVocab.collectPharmacy';
    if (isStore)    return 'deliveryVocab.collectStore';
    return 'deliveryVocab.collectRestaurant';
  }
  // Unknown variant — safe fallback
  return 'deliveryVocab.atPickupRestaurant';
}
