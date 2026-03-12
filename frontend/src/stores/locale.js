import { defineStore } from "pinia";
import { DEFAULT_LOCALE, detectBrowserLocale, getLocaleDirection, normalizeLocale } from "../i18n/config";

const storageKey = () => {
  if (typeof window === "undefined") return "resto.locale";
  return `resto.locale:${window.location.hostname || "default"}`;
};

const readStoredLocale = () => {
  if (typeof window === "undefined") return "";
  try {
    return String(window.localStorage.getItem(storageKey()) || "").trim();
  } catch {
    return "";
  }
};

const writeStoredLocale = (value) => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(storageKey(), value);
  } catch {
    // Ignore storage write failures and keep runtime locale only.
  }
};

const applyDocumentLocale = (locale) => {
  if (typeof document === "undefined") return;
  const resolved = normalizeLocale(locale);
  const direction = getLocaleDirection(resolved);
  document.documentElement.lang = resolved;
  document.documentElement.dir = direction;
  document.body?.setAttribute("dir", direction);
};

export const useLocaleStore = defineStore("locale", {
  state: () => ({
    current: DEFAULT_LOCALE,
    tenantDefault: DEFAULT_LOCALE,
    hydrated: false,
    userOverridden: false,
  }),
  getters: {
    isRtl(state) {
      return getLocaleDirection(state.current) === "rtl";
    },
  },
  actions: {
    bootstrap(options = {}) {
      if (this.hydrated) {
        if (options.tenantDefault) this.setTenantDefault(options.tenantDefault);
        return;
      }

      const tenantDefault = normalizeLocale(options.tenantDefault || DEFAULT_LOCALE);
      const rawStored = readStoredLocale();
      const stored = rawStored ? normalizeLocale(rawStored) : "";
      const browser = detectBrowserLocale();
      const next = stored || tenantDefault || browser || DEFAULT_LOCALE;

      this.tenantDefault = tenantDefault;
      this.current = normalizeLocale(next);
      this.userOverridden = Boolean(stored);
      this.hydrated = true;
      applyDocumentLocale(this.current);
    },
    setTenantDefault(locale) {
      const next = normalizeLocale(locale || DEFAULT_LOCALE);
      this.tenantDefault = next;
      if (!this.userOverridden) {
        this.current = next;
        applyDocumentLocale(this.current);
      }
    },
    setLocale(locale, options = {}) {
      const resolved = normalizeLocale(locale);
      this.current = resolved;
      if (options.userOverride !== false) {
        this.userOverridden = true;
      }
      if (options.persist !== false) {
        writeStoredLocale(resolved);
      }
      applyDocumentLocale(resolved);
    },
  },
});
