/**
 * Reactive locale-message store with lazy-loading for non-default locales.
 *
 * - EN is bundled synchronously (the default locale, needed on first paint).
 * - FR and AR are dynamically imported when first requested, so Vite splits
 *   them into separate chunks that are only fetched on locale switch.
 *
 * The verify-i18n scripts import messages.js directly (Node.js static import)
 * so they are unaffected by this change.
 */

import { reactive } from "vue";
import enMessages from "./messages-en.js";
import { DEFAULT_LOCALE } from "./config.js";

// ---------------------------------------------------------------------------
// Arabic merge helpers (mirrors the logic in messages.js)
// ---------------------------------------------------------------------------

const isPlainObject = (value) =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const isCorruptedTranslation = (value) => {
  if (typeof value !== "string") return false;
  const normalized = value.trim();
  if (!normalized) return false;
  if (
    /[ÃÂØÙÐ]/.test(normalized) &&
    !/[؀-ۿ]/.test(normalized)
  )
    return true;
  if (!normalized.includes("?")) return false;
  return normalized.replace(/[\s?.,:;!()[\]{}%0-9/+\\-]/g, "").length === 0;
};

const cloneLocaleValue = (value) => {
  if (Array.isArray(value)) return value.map(cloneLocaleValue);
  if (isPlainObject(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, cloneLocaleValue(item)])
    );
  }
  return value;
};

const mergeLocaleInto = (target, source) => {
  if (!isPlainObject(source)) return target;
  Object.entries(source).forEach(([key, value]) => {
    if (isCorruptedTranslation(value)) return;
    if (Array.isArray(value)) {
      target[key] = value.map(cloneLocaleValue);
      return;
    }
    if (isPlainObject(value)) {
      target[key] = mergeLocaleInto(
        isPlainObject(target[key]) ? target[key] : {},
        value
      );
      return;
    }
    if (value !== undefined) target[key] = value;
  });
  return target;
};

// ---------------------------------------------------------------------------
// Reactive catalog store
// EN is synchronously available; others load on demand.
// ---------------------------------------------------------------------------

/**
 * catalog holds the resolved (merged) message objects per locale code.
 * Using reactive() so that components re-render when a new locale loads.
 */
export const catalog = reactive({
  en: enMessages,
});

/** Tracks in-flight or completed dynamic-import promises to avoid double-loading. */
const loading = {};

/**
 * Ensure the given locale's catalog is loaded. Returns a Promise that
 * resolves once the catalog is ready (immediately for already-loaded locales).
 *
 * @param {string} locale - normalised locale code e.g. "en", "fr", "ar"
 */
export const ensureLocale = async (locale) => {
  if (catalog[locale]) return; // already loaded
  if (loading[locale]) return loading[locale]; // in flight

  let promise;
  if (locale === "fr") {
    promise = import("./messages-fr.js").then((mod) => {
      catalog[locale] = mod.default;
    });
  } else if (locale === "ar") {
    promise = import("./messages-ar.js").then((mod) => {
      catalog[locale] = mergeLocaleInto(cloneLocaleValue(enMessages), mod.default);
    });
  } else {
    return; // unknown locale → EN fallback at call sites; nothing to load.
  }

  // Evict the in-flight entry if the chunk fetch fails (flaky network, CDN 404)
  // so a later call can retry instead of replaying the rejected promise forever.
  loading[locale] = promise.catch((err) => {
    delete loading[locale];
    throw err;
  });
  return loading[locale];
};

/**
 * Synchronous message lookup. Falls back to EN for any key not in the
 * requested locale (which may still be loading).
 */
export const getMessages = (locale) =>
  catalog[locale] ?? catalog[DEFAULT_LOCALE];
