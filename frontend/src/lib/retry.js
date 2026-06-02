// Transient-failure retry policy for the API client (src/lib/api.js).
//
// Kept as pure functions so the "what should we retry?" decision — the part that
// matters for correctness — is unit-tested without standing up axios. On flaky
// restaurant WiFi a single dropped packet shouldn't surface as a failed order
// list or a broken dashboard; a couple of quick retries smooth that over.

export const MAX_RETRIES = 2;

// Only idempotent methods are safe to replay. POST/PUT/PATCH/DELETE are never
// retried automatically — a retried mutation risks double-submitting (e.g. two
// orders, two charges).
export const isIdempotentMethod = (method) =>
  ["get", "head", "options"].includes(String(method || "get").toLowerCase());

// Retry only transient failures a repeat might actually fix:
//   • genuine network errors (connection refused/reset, DNS, offline) → retry
//   • 5xx server errors → retry
//   • timeouts (ECONNABORTED) → do NOT retry (would stack more 30s waits)
//   • cancelled requests → never retry
//   • 4xx incl. 401/403/404/422/429 → never retry (not transient)
export const isRetriableError = (error) => {
  const code = error?.code;
  if (code === "ERR_CANCELED" || code === "ECONNABORTED") return false;
  const status = error?.response?.status;
  if (status === undefined) return true; // no response → network-level failure
  return status >= 500 && status <= 599;
};

export const shouldRetry = (error, attempt) => {
  if (attempt >= MAX_RETRIES) return false;
  if (!error?.config) return false;
  return isIdempotentMethod(error.config.method) && isRetriableError(error);
};

// 300ms, 600ms, 1200ms … plus optional jitter the caller passes in.
export const retryBackoffMs = (attempt, jitter = 0) =>
  Math.round(300 * Math.pow(2, attempt) + jitter);
