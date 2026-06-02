/**
 * Generate a unique idempotency key for a money-moving request.
 *
 * The caller should keep one key for a given logical action and reuse it on retries
 * (e.g. a lost-response resubmit) so the server dedups instead of double-charging,
 * then discard it after a confirmed success so the next action gets a fresh key.
 */
export function newIdempotencyKey() {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
  } catch {
    /* fall through */
  }
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}
