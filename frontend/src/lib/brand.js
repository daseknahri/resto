/**
 * Central platform brand constants — single source of truth for the umbrella
 * "Kepoli" super-app brand used across code (document titles, PWA join pages,
 * fallbacks). Per-tenant restaurant/store names are NOT controlled here — each
 * tenant keeps its own name (tenant.meta.name); this is only the PLATFORM brand.
 *
 * Displayed marketing copy lives in i18n (so it can be localized); use these
 * constants for code-level references that should stay consistent everywhere.
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

export default {
  PLATFORM_NAME,
  PLATFORM_NAME_LOWER,
  PLATFORM_TAGLINE,
  PLATFORM_DESCRIPTION,
  PLATFORM_MONOGRAM,
};
