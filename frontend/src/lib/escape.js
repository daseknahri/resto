/**
 * Escape a value for safe interpolation into an HTML string.
 * Use wherever user-supplied data is injected via document.write / template literals.
 */
export const escapeHtml = (v) =>
  String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
