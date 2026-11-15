/**
 * Shared phone helpers (Run 8 / S1-I, B-15).
 *
 * Mirrors backend/accounts/phone.py `normalize_e164` ("normalize, never guess"):
 * a wa.me link built from raw digits is dead for every national-format number
 * ("06…" -> wa.me/0612345678 never resolves), so the country code must be
 * restored before the link is built. The tenant default dial code is 212 (MAD);
 * no per-tenant dial-code setting exists, so callers that know better pass it in.
 *
 * - "+…"  -> digits kept (already international)
 * - "00…" -> international prefix, digits kept
 * - "0…"  -> "<defaultDialCode>…" (national trunk -> international)
 * - "<defaultDialCode>…" (e.g. "212…") -> kept (international, "+" omitted)
 * - anything else (bare digits, no country context) -> "" (refuse to guess)
 */

/** Tenant default dial code (MAD). No per-tenant dial-code setting exists. */
export const DEFAULT_DIAL_CODE = "212";

/**
 * Normalize a free-form phone into wa.me digits (no leading "+").
 * Returns "" when the number cannot be confidently resolved.
 */
export function toWaPhone(raw, defaultDialCode = DEFAULT_DIAL_CODE) {
  const cleaned = String(raw || "")
    .replace(/[^\d+]/g, "")
    .replace(/(?!^)\+/g, "");
  if (!cleaned) return "";
  const cc = String(defaultDialCode || "").replace(/\D/g, "");
  let digits;
  if (cleaned.startsWith("+")) {
    digits = cleaned.slice(1);
  } else if (cleaned.startsWith("00")) {
    digits = cleaned.slice(2);
  } else if (cleaned.startsWith("0")) {
    if (!cc) return "";
    digits = cc + cleaned.slice(1);
  } else if (cc && cleaned.startsWith(cc)) {
    digits = cleaned;
  } else {
    return ""; // bare digits with no country context — refuse to guess
  }
  // wa.me numbers are 6–15 digits and never start with 0 after the country code.
  if (!/^\d{6,15}$/.test(digits) || digits.startsWith("0")) return "";
  return digits;
}

/**
 * Build a wa.me link for a free-form phone. Returns "" when unresolvable
 * (callers hide the link / fall back instead of emitting a dead link).
 */
export function toWhatsappUrl(raw, defaultDialCode = DEFAULT_DIAL_CODE) {
  const digits = toWaPhone(raw, defaultDialCode);
  return digits ? `https://wa.me/${digits}` : "";
}
