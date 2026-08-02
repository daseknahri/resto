// Delivery-pricing primitives shared by the tenant storefront (Cart.vue) and the platform
// marketplace (MarketplaceMenuPage.vue). These were copied verbatim in both pages; extracting
// them here removes the drift risk on money/geo math. Pure functions — they mirror the backend
// (tenancy/delivery_pricing.valid_coord + tenancy/routing road-factor / avg-speed) so the client
// fee/ETA preview lines up with the server's authoritative figure.

// Straight-line → driven-distance multiplier (DELIVERY_ROAD_FACTOR, default 1.3 on the server).
export const ROAD_FACTOR = 1.3;

// Average driving speed for the travel-time estimate (matches backend tenancy/routing.AVG_SPEED_KMH).
export const AVG_SPEED_KMH = 22;

// Great-circle distance in km between two points, or null if any coordinate is non-finite.
export function haversineKm(lat1, lng1, lat2, lng2) {
  const toNum = (v) => (v === null || v === undefined || v === '' ? NaN : Number(v));
  const a1 = toNum(lat1), o1 = toNum(lng1), a2 = toNum(lat2), o2 = toNum(lng2);
  if (![a1, o1, a2, o2].every((n) => Number.isFinite(n))) return null;
  const R = 6371.0088;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(a2 - a1);
  const dLng = rad(o2 - o1);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a1)) * Math.cos(rad(a2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.asin(Math.min(1, Math.sqrt(s)));
}

// A coordinate is usable only if it's finite, in range, AND not the null-island (0,0) default a
// failed locate/geocode leaves behind — mirrors backend valid_coord.
export function validCoord(lat, lng) {
  const a = Number(lat), o = Number(lng);
  if (!Number.isFinite(a) || !Number.isFinite(o)) return false;
  if (a < -90 || a > 90 || o < -180 || o > 180) return false;
  return !(Math.abs(a) < 1e-6 && Math.abs(o) < 1e-6);
}
