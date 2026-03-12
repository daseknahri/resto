export const DEFAULT_LOCALE = "en";

export const LOCALE_OPTIONS = [
  { code: "en", label: "English", nativeLabel: "EN", dir: "ltr" },
  { code: "fr", label: "French", nativeLabel: "FR", dir: "ltr" },
  { code: "ar", label: "Arabic", nativeLabel: "عربي", dir: "rtl" },
];

const SUPPORTED = new Set(LOCALE_OPTIONS.map((option) => option.code));
const RTL = new Set(LOCALE_OPTIONS.filter((option) => option.dir === "rtl").map((option) => option.code));

export const normalizeLocale = (value) => {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return DEFAULT_LOCALE;
  const primary = raw.split(/[-_]/)[0];
  return SUPPORTED.has(primary) ? primary : DEFAULT_LOCALE;
};

export const getLocaleOption = (value) => {
  const code = normalizeLocale(value);
  return LOCALE_OPTIONS.find((option) => option.code === code) || LOCALE_OPTIONS[0];
};

export const getLocaleDirection = (value) => (RTL.has(normalizeLocale(value)) ? "rtl" : "ltr");

export const detectBrowserLocale = () => {
  if (typeof navigator === "undefined") return DEFAULT_LOCALE;
  const candidates = Array.isArray(navigator.languages) && navigator.languages.length
    ? navigator.languages
    : [navigator.language];
  const resolved = candidates.find(Boolean);
  return normalizeLocale(resolved);
};
