/**
 * Bearer-token hygiene for URLs.
 *
 * Activation / password-reset links carry a live credential (`?token=…`). Once a
 * page has read it into component state it must not linger in the address bar
 * (history, screenshots, shoulder-surfing, Referer), and it must never reach
 * Sentry (pageload `request.url`, navigation / xhr breadcrumbs).
 */

export const REDACTED = "[redacted]";

// `token=<v>` in a query (raw or URL-encoded, also matches access_token= etc.)
const TOKEN_PARAM_RE = /(token=|token%3D)([^&#\s"'<>]+)/gi;
// Bearer links that carry the token as a path segment.
const TOKEN_PATH_RE = /(\/(?:activate|reset-password|r|track)\/)([^/?#\s"'<>]+)/gi;

export function redactTokensInUrl(value) {
  if (typeof value !== "string" || !value) return value;
  return value.replace(TOKEN_PARAM_RE, `$1${REDACTED}`).replace(TOKEN_PATH_RE, `$1${REDACTED}`);
}

const MAX_DEPTH = 8;
// SDK-internal bookkeeping (scopes, sampling context) — never user data, never touched.
const SKIP_KEYS = new Set(["sdkProcessingMetadata"]);

const isPlainObject = (value) => {
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};

function scrubInPlace(value, depth) {
  if (depth > MAX_DEPTH || !value || typeof value !== "object") return;
  if (!Array.isArray(value) && !isPlainObject(value)) return;
  for (const key of Object.keys(value)) {
    if (SKIP_KEYS.has(key)) continue;
    const item = value[key];
    if (typeof item === "string") {
      const redacted = redactTokensInUrl(item);
      if (redacted !== item) value[key] = redacted;
    } else {
      scrubInPlace(item, depth + 1);
    }
  }
}

/**
 * Sentry `beforeSend` / `beforeSendTransaction` / `beforeBreadcrumb` hook: redacts
 * tokens in every string of the (JSON-shaped) event or breadcrumb — request.url,
 * Referer, transaction name, breadcrumb data.url / from / to, messages — in place.
 */
export function scrubSentryPayload(payload) {
  scrubInPlace(payload, 0);
  return payload;
}

/**
 * Remove `token` from the current route's query (keeping every other param) once
 * the page has copied it into its own state. Best-effort: a navigation failure
 * must never break the form.
 */
export function stripTokenFromUrl(route, router) {
  const query = route?.query;
  if (!query || !Object.prototype.hasOwnProperty.call(query, "token")) return;
  const rest = { ...query };
  delete rest.token;
  try {
    Promise.resolve(router.replace({ path: route.path, query: rest, hash: route.hash })).catch(() => {});
  } catch {
    // ignore — the token still works from component state
  }
}
