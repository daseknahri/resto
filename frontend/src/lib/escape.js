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

/**
 * Sanitize an external URL for use as an <a href>.
 *
 * Returns the URL unchanged when it starts with http:// or https://.
 * Returns "" for anything else (javascript:, data:, vbscript:, bare paths, …)
 * so the link is suppressed rather than executing script.
 *
 * Server-side: Django URLField already rejects non-http(s) schemes, but this
 * provides a client-side defence-in-depth layer for any value that reaches
 * the frontend (e.g. direct DB edits, legacy data).
 *
 * @param {string} url
 * @returns {string}
 */
export const safeExternalUrl = (url) => {
  const s = String(url ?? "").trim();
  return s.startsWith("http://") || s.startsWith("https://") ? s : "";
};
