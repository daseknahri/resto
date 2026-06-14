/**
 * Platform pricing scaffold — config-driven, owner-configurable.
 *
 * TODO owner: replace the placeholder amounts below with real prices before
 * going live. The "price" field is a string so you can write "Free",
 * "Contact us", or "49.00". The "period" field is an i18n key suffix
 * (e.g. "monthly" → t("pricing.period.monthly")).
 *
 * Each plan is also imported by Home.vue to drive the plan cards. Keeping
 * amounts here means ONE place to edit for the whole marketing site.
 */

export const PRICING_PLANS = [
  {
    code: "basic",
    // TODO owner: set price — e.g. "49.00" (MAD/month)
    price: null,
    period: "monthly",
    recommended: true,
  },
  {
    code: "growth",
    // TODO owner: set price — e.g. "149.00" (MAD/month)
    price: null,
    period: "monthly",
    recommended: false,
  },
  {
    code: "pro",
    // TODO owner: set price — contact sales or set a fixed amount
    price: null,
    period: "monthly",
    recommended: false,
  },
];

/** Convenience lookup by plan code */
export const getPlanPricing = (code) =>
  PRICING_PLANS.find((p) => p.code === code) ?? null;

export default PRICING_PLANS;
