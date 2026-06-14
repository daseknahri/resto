// Pre-hydration locale/direction boot. Runs synchronously in <head> BEFORE the
// Vue app paints so the very first render (and assistive tech / crawlers that
// honour client JS) sees the correct <html lang>/<dir> instead of the static
// en/LTR baseline. stores/locale.js only updates documentElement AFTER hydration.
//
// Kept external (not inline) so the Content-Security-Policy can stay strict
// script-src 'self' without 'unsafe-inline' or a per-build hash.
//
// KEEP IN SYNC: the supported codes, default, and RTL set below mirror
//   src/i18n/config.js   (LOCALE_OPTIONS / DEFAULT_LOCALE / getLocaleDirection)
//   src/stores/locale.js (storageKey + applyDocumentLocale)
// If the locale list changes, update all three.
(function () {
  var SUPPORTED = ['en', 'fr', 'ar']; // mirror i18n/config.js LOCALE_OPTIONS codes
  var DEFAULT_LOCALE = 'en';          // mirror i18n/config.js DEFAULT_LOCALE
  var RTL = { ar: true };             // mirror i18n/config.js dir:"rtl" entries

  function normalize(value) {
    var raw = String(value || '').trim().toLowerCase();
    if (!raw) return DEFAULT_LOCALE;
    var primary = raw.split(/[-_]/)[0];
    return SUPPORTED.indexOf(primary) !== -1 ? primary : DEFAULT_LOCALE;
  }

  function direction(code) {
    return RTL[code] ? 'rtl' : 'ltr'; // mirror getLocaleDirection
  }

  // Mirror stores/locale.js storageKey(): "resto.locale:" + hostname.
  var stored = '';
  try {
    var key = 'resto.locale:' + (window.location.hostname || 'default');
    stored = String(window.localStorage.getItem(key) || '').trim();
  } catch (e) {
    stored = '';
  }

  // Resolution: stored user override -> browser language -> default. NOTE: this is a
  // best-effort baseline. The store's bootstrap() also weighs the tenant's default locale
  // (tenantDefault), which we cannot know here without a network call. So a tenant whose
  // default is RTL (ar), visited with no stored override and a non-Arabic browser, paints
  // LTR for one frame and is corrected to RTL at hydration. The common stored-override case
  // is handled exactly.
  var locale = normalize(stored || (navigator && navigator.language) || DEFAULT_LOCALE);
  var dir = direction(locale);

  var docEl = document.documentElement;
  if (docEl) {
    docEl.lang = locale;
    docEl.dir = dir;
  }
  // body may not exist yet when this runs in <head>; guard it.
  if (document.body) {
    document.body.setAttribute('dir', dir);
  }
})();
