import { normalizeLocale, DEFAULT_LOCALE } from "./config";
import { messages } from "./messages";
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

const currentLocale = () => {
  try {
    const locale = useLocaleStore();
    return normalizeLocale(locale.current);
  } catch {
    return DEFAULT_LOCALE;
  }
};

export const translate = (key, params = {}) => {
  const locale = currentLocale();
  const value = getByPath(messages[locale], key) ?? getByPath(messages[DEFAULT_LOCALE], key) ?? key;
  return interpolate(value, params);
};
