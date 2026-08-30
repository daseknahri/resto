/**
 * Cached Intl.*Format factories
 * ==============================
 * Constructing an `Intl.NumberFormat` / `Intl.DateTimeFormat` resolves CLDR
 * locale data and is ~10-100x the cost of calling `.format()` on an existing
 * instance. The app's shared formatters (currency store `formatPrice`, and the
 * `useI18n` `formatNumber` / `formatCurrency` / `formatDateTime`) are invoked
 * from `v-for` template bindings — a large marketplace menu can trigger hundreds
 * of formatter calls per render pass, re-paid on every re-render.
 *
 * These helpers memoize the formatter instances, keyed by every output-affecting
 * input (locale + the full options object, which for currency formatting already
 * carries the currency code). A different locale, currency, or option shape maps
 * to a different cache entry, so switching currency/locale still selects the
 * correct formatter. The `.format()` call and its output are unchanged.
 *
 * This module intentionally imports nothing from the app (no store/composable)
 * so it can be shared by both the currency store and useI18n without any risk
 * of an import cycle.
 */

const numberFormatters = new Map();
const dateTimeFormatters = new Map();

// Stable key across all inputs that affect the formatter's output. JSON.stringify
// of the options object is deterministic here because the callers always build the
// options in the same key order, and `undefined` option values (dropped by
// stringify) are treated as "unspecified" by Intl too — so the key and the Intl
// behavior stay in lockstep.
const cacheKey = (locale, options) => `${locale}|${JSON.stringify(options ?? {})}`;

/**
 * Return a cached `Intl.NumberFormat` for the given locale + options, creating
 * (and caching) one on first use. Throws exactly as `new Intl.NumberFormat`
 * would (e.g. an invalid currency code) — a failed construction is not cached.
 */
export function getNumberFormat(locale, options = {}) {
  const key = cacheKey(locale, options);
  let formatter = numberFormatters.get(key);
  if (!formatter) {
    formatter = new Intl.NumberFormat(locale, options);
    numberFormatters.set(key, formatter);
  }
  return formatter;
}

/**
 * Return a cached `Intl.DateTimeFormat` for the given locale + options, creating
 * (and caching) one on first use. Throws exactly as `new Intl.DateTimeFormat`
 * would — a failed construction is not cached.
 */
export function getDateTimeFormat(locale, options = {}) {
  const key = cacheKey(locale, options);
  let formatter = dateTimeFormatters.get(key);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat(locale, options);
    dateTimeFormatters.set(key, formatter);
  }
  return formatter;
}
