// Derive "recent recipients" and "recent drop-off addresses" from a rider's
// package history (the items already returned by GET /api/rides/history/ with
// kind === 'package'). Pure, client-side, no backend call — the recipient PII
// (name + phone) is the rider's own, already present on each history row.
//
// Used by SendPackagePage.vue to offer 1-tap re-fill of a previous recipient,
// matching the Uber Connect / Glovo "send to a recent contact" pattern.

/**
 * Most-recent DISTINCT recipients (by normalized phone, falling back to name).
 * Newest first. Skips rows with neither a name nor a phone.
 *
 * @param {Array<object>} history  rows from /rides/history/ (any kind)
 * @param {number} limit           max chips to return (default 4)
 * @returns {Array<{name: string, phone: string}>}
 */
export function recentRecipients(history, limit = 4) {
  if (!Array.isArray(history)) return [];
  const out = [];
  const seen = new Set();
  for (const row of history) {
    if (!row || row.kind !== 'package') continue;
    const name = String(row.recipient_name || '').trim();
    const phone = String(row.recipient_phone || '').trim();
    if (!name && !phone) continue;
    // Dedupe key: phone digits if present, else lowercased name.
    const key = phone ? phone.replace(/\D/g, '') : name.toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push({ name, phone });
    if (out.length >= limit) break;
  }
  return out;
}

/**
 * Most-recent DISTINCT drop-off addresses from package history. Newest first.
 * Includes lat/lng when the row carried them so a tap can recenter the map.
 *
 * @param {Array<object>} history  rows from /rides/history/ (any kind)
 * @param {number} limit           max chips to return (default 3)
 * @returns {Array<{address: string, lat: (number|null), lng: (number|null)}>}
 */
export function recentDropoffs(history, limit = 3) {
  if (!Array.isArray(history)) return [];
  const out = [];
  const seen = new Set();
  for (const row of history) {
    if (!row || row.kind !== 'package') continue;
    const address = String(row.dropoff_address || '').trim();
    if (!address) continue;
    const key = address.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    // Number(null) === 0, so guard against null/undefined/'' before coercing.
    const rawLat = row.dropoff_lat;
    const rawLng = row.dropoff_lng;
    const lat = rawLat == null || rawLat === '' ? NaN : Number(rawLat);
    const lng = rawLng == null || rawLng === '' ? NaN : Number(rawLng);
    out.push({
      address,
      lat: Number.isFinite(lat) ? lat : null,
      lng: Number.isFinite(lng) ? lng : null,
    });
    if (out.length >= limit) break;
  }
  return out;
}
