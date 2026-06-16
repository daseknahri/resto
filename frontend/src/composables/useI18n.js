import { computed } from "vue";
import { DEFAULT_LOCALE, LOCALE_OPTIONS, getLocaleDirection, normalizeLocale } from "../i18n/config";
import { catalog, ensureLocale, getMessages } from "../i18n/localeLoader";
import { useLocaleStore } from "../stores/locale";
import { useCurrencyStore } from "../stores/currency";

const getByPath = (target, path) =>
  String(path || "")
    .split(".")
    .filter(Boolean)
    .reduce((value, part) => (value && typeof value === "object" ? value[part] : undefined), target);

const interpolate = (template, params = {}) =>
  String(template || "").replace(/\{(\w+)\}/g, (_, key) => {
    const value = params[key];
    return value === undefined || value === null ? "" : String(value);
  });

const resolveMessage = (locale, key) => {
  const resolvedLocale = normalizeLocale(locale);
  const msgs = getMessages(resolvedLocale);
  return getByPath(msgs, key) ?? getByPath(catalog[DEFAULT_LOCALE], key) ?? key;
};

export const useI18n = () => {
  const locale = useLocaleStore();
  const currency = useCurrencyStore();

  const currentLocale = computed(() => normalizeLocale(locale.current));
  const localeOptions = LOCALE_OPTIONS;

  const t = (key, params = {}) => interpolate(resolveMessage(currentLocale.value, key), params);

  const formatNumber = (value, options = {}) =>
    new Intl.NumberFormat(currentLocale.value, options).format(Number.isFinite(Number(value)) ? Number(value) : 0);

  const formatCurrency = (value, currency = "USD", options = {}) =>
    new Intl.NumberFormat(currentLocale.value, {
      style: "currency",
      currency: currency || "MAD",
      ...options,
    }).format(Number.isFinite(Number(value)) ? Number(value) : 0);

  const formatDateTime = (value, options = {}) => {
    if (!value) return "";
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat(currentLocale.value, {
      dateStyle: "medium",
      timeStyle: "short",
      ...options,
    }).format(date);
  };

  const itemCountLabel = (count) =>
    count === 1
      ? t("common.item_one", { count })
      : t("common.item_other", { count });

  /**
   * Format a MAD price in the customer's selected display currency.
   * Replaces direct formatCurrency(price, dish.currency) calls on customer-facing pages.
   */
  const formatPrice = (madAmount) => currency.formatPrice(madAmount, currentLocale.value);

  /**
   * Switch locale: lazy-load the catalog if needed, then set it.
   * Returns a Promise so callers can await the load before switching.
   */
  const setLocale = async (value) => {
    const resolved = normalizeLocale(value);
    try {
      await ensureLocale(resolved);
    } catch {
      // Locale chunk failed to load (e.g. flaky network) — keep the current
      // locale rather than switching to a catalog that falls back to EN strings
      // (and, for Arabic, would leave RTL applied over English text). The loader
      // evicts its cache on failure, so a later attempt can retry.
      return false;
    }
    locale.setLocale(resolved);
    return true;
  };

  return {
    currentLocale,
    localeOptions,
    isRtl: computed(() => getLocaleDirection(currentLocale.value) === "rtl"),
    t,
    setLocale,
    formatNumber,
    formatCurrency,
    formatPrice,
    formatDateTime,
    itemCountLabel,
  };
};
