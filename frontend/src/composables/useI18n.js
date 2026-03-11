import { computed } from "vue";
import { DEFAULT_LOCALE, LOCALE_OPTIONS, getLocaleDirection, normalizeLocale } from "../i18n/config";
import { messages } from "../i18n/messages";
import { useLocaleStore } from "../stores/locale";

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
  return getByPath(messages[resolvedLocale], key) ?? getByPath(messages[DEFAULT_LOCALE], key) ?? key;
};

export const useI18n = () => {
  const locale = useLocaleStore();

  const currentLocale = computed(() => normalizeLocale(locale.current));
  const localeOptions = LOCALE_OPTIONS;

  const t = (key, params = {}) => interpolate(resolveMessage(currentLocale.value, key), params);

  const formatNumber = (value, options = {}) =>
    new Intl.NumberFormat(currentLocale.value, options).format(Number.isFinite(Number(value)) ? Number(value) : 0);

  const formatCurrency = (value, currency = "USD", options = {}) =>
    new Intl.NumberFormat(currentLocale.value, {
      style: "currency",
      currency: currency || "USD",
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

  return {
    currentLocale,
    localeOptions,
    isRtl: computed(() => getLocaleDirection(currentLocale.value) === "rtl"),
    t,
    setLocale: (value) => locale.setLocale(value),
    formatNumber,
    formatCurrency,
    formatDateTime,
    itemCountLabel,
  };
};
