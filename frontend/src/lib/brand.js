/**
 * Central platform brand constants — single source of truth for the umbrella
 * "Kepoli" super-app brand used across code (document titles, PWA join pages,
 * fallbacks). Per-tenant restaurant/store names are NOT controlled here — each
 * tenant keeps its own name (tenant.meta.name); this is only the PLATFORM brand.
 *
 * Displayed marketing copy lives in i18n (so it can be localized); use these
 * constants for code-level references that should stay consistent everywhere.
 *
 * Domain / contact are read from VITE_* env vars so a single .env change
 * rebrands every user-facing marketing string. Fallbacks are Kepoli-branded
 * (never a dev subdomain).
 */

export const PLATFORM_NAME = "Kepoli";
export const PLATFORM_NAME_LOWER = "kepoli";
// Short positioning line for the everything/super app (food, shops, delivery).
export const PLATFORM_TAGLINE = "Order. Delivered. Earn.";
// Longer descriptor used in PWA/app-store style contexts.
export const PLATFORM_DESCRIPTION =
  "Order from restaurants and shops, get it delivered, or earn as a rider — all on Kepoli.";
// Monogram shown in the logo tile.
export const PLATFORM_MONOGRAM = "K";

/**
 * Public-facing brand domain shown in hero/CTA copy.
 * Set VITE_BRAND_DOMAIN in .env (e.g. "menu.kepoli.app") to override.
 */
export const BRAND_DOMAIN =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_BRAND_DOMAIN) ||
  "menu.kepoli.app";

/**
 * Support / contact email shown in legal pages, landing footer, etc.
 * Set VITE_SUPPORT_EMAIL in .env to override.
 */
export const SUPPORT_EMAIL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_SUPPORT_EMAIL) ||
  "contact@kepoli.app";

/**
 * Public demo menu URL (used in hero cards and demo landing).
 * Set VITE_PUBLIC_DEMO_URL in .env to override.
 */
export const DEMO_MENU_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_PUBLIC_DEMO_URL) ||
  `https://${BRAND_DOMAIN}/menu`;

export default {
  PLATFORM_NAME,
  PLATFORM_NAME_LOWER,
  PLATFORM_TAGLINE,
  PLATFORM_DESCRIPTION,
  PLATFORM_MONOGRAM,
  BRAND_DOMAIN,
  SUPPORT_EMAIL,
  DEMO_MENU_URL,
};
