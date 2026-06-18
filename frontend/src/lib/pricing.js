/**
 * Platform pricing scaffold — config-driven, owner-configurable.
 *
 * Prices come from the backend (GET /api/public/plans/) which the owner sets
 * in the Django admin. The static PRICING_PLANS below define UI structure
 * (recommended flag, period); price_monthly is populated live from the API.
 *
 * Until the owner sets prices, the "price" field is null and the marketing
 * page shows a "Price TBD" badge.
 */

export const PRICING_PLANS = [
  {
    code: "basic",
    period: "monthly",
    recommended: true,
  },
  {
    code: "growth",
    period: "monthly",
    recommended: false,
  },
  {
    code: "pro",
    period: "monthly",
    recommended: false,
  },
];

/** Convenience lookup by plan code */
export const getPlanPricing = (code) =>
  PRICING_PLANS.find((p) => p.code === code) ?? null;

/**
 * Fetch live pricing from the backend.
 * Returns a map of { code → { price_monthly, currency, billing_period } }.
 * Falls back to an empty map on network error (marketing page degrades gracefully
 * to "Price TBD" rather than breaking).
 */
export async function fetchPlanPricing() {
  try {
    const res = await fetch("/api/public/plans/", { credentials: "omit" });
    if (!res.ok) return {};
    const data = await res.json();
    return Object.fromEntries(
      Array.isArray(data) ? data.map((p) => [p.code, p]) : []
    );
  } catch {
    return {};
  }
}

export default PRICING_PLANS;
