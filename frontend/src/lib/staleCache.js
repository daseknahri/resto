/**
 * Lightweight stale-while-revalidate (SWR) cache backed by localStorage.
 *
 * Each entry is automatically scoped to:
 *   hostname  — so multi-tenant deployments never share cache entries
 *   locale    — so language switches always get freshly-translated content
 *
 * Usage pattern in a store:
 *
 *   import { readCache, isFresh, writeCache } from "../lib/staleCache"
 *
 *   const CACHE = "meta"
 *   const TTL   = 5 * 60 * 1000  // 5 min
 *
 *   async fetchMeta() {
 *     const cached = readCache(CACHE)
 *     if (cached) {
 *       this.data = cached                // instant render from cache
 *       if (isFresh(CACHE, TTL)) return   // still fresh → skip network
 *       // stale → fall through to background revalidate (no spinner)
 *     } else {
 *       this.loading = true               // first visit → show spinner
 *     }
 *     try {
 *       const res = await api.get(...)
 *       this.data = res.data
 *       writeCache(CACHE, res.data)
 *     } finally { this.loading = false }
 *   }
 */

const PREFIX = "resto.cache"

/** Current locale from the live document (set by locale store) */
const getLocale = () => {
  if (typeof document === "undefined") return "en"
  return (document.documentElement?.lang || "en").toLowerCase().trim() || "en"
}

/** Hostname for key scoping */
const getHostname = () => {
  if (typeof window === "undefined") return "local"
  return window.location.hostname || "local"
}

/** Build a storage key scoped to current host + locale */
export const makeCacheKey = (name) =>
  `${PREFIX}:${getHostname()}:${getLocale()}:${name}`

// ── Internal helpers ──────────────────────────────────────────────────────────

const safeRead = (key) => {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

const safeWrite = (key, payload) => {
  try {
    localStorage.setItem(key, JSON.stringify(payload))
  } catch {
    // Storage full or unavailable — silently skip.
    // The app continues to work perfectly via network; cache is best-effort.
  }
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Return the cached data for `name`, or null if nothing is stored.
 * Does NOT check freshness — call isFresh() for that.
 */
export const readCache = (name) => {
  const entry = safeRead(makeCacheKey(name))
  return entry?.data ?? null
}

/**
 * True if a cache entry exists AND was written less than `ttlMs` ago.
 */
export const isFresh = (name, ttlMs) => {
  const entry = safeRead(makeCacheKey(name))
  if (!entry?.ts) return false
  return Date.now() - entry.ts < ttlMs
}

/**
 * Persist `data` under `name` with the current timestamp.
 */
export const writeCache = (name, data) => {
  safeWrite(makeCacheKey(name), { ts: Date.now(), data })
}

/**
 * Remove a cache entry. Call this when the owner saves changes so
 * the next customer load gets fresh data instead of stale.
 */
export const bustCache = (name) => {
  try {
    localStorage.removeItem(makeCacheKey(name))
  } catch {
    // ignore
  }
}
