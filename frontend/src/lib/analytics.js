import api from "./api";

const SESSION_KEY = "resto.analytics.session_id";
const seenEventKeys = new Set();

const toShortString = (value, maxLen) => String(value || "").trim().slice(0, maxLen);

const getSessionId = () => {
  if (typeof window === "undefined") return "";
  try {
    const existing = window.sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const generated = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    window.sessionStorage.setItem(SESSION_KEY, generated);
    return generated;
  } catch (err) {
    return "";
  }
};

const safeMetadata = (value) => {
  if (!value || typeof value !== "object") return {};
  const result = {};
  Object.entries(value).forEach(([key, raw]) => {
    const safeKey = toShortString(key, 48);
    if (!safeKey) return;
    if (typeof raw === "string") {
      result[safeKey] = raw.slice(0, 160);
      return;
    }
    if (typeof raw === "number" || typeof raw === "boolean" || raw === null) {
      result[safeKey] = raw;
      return;
    }
    if (Array.isArray(raw)) {
      result[safeKey] = raw.slice(0, 10).map((item) => toShortString(item, 80));
      return;
    }
    result[safeKey] = toShortString(JSON.stringify(raw), 160);
  });
  return result;
};

export const trackEvent = (eventType, payload = {}, options = {}) => {
  if (typeof window === "undefined") return;
  const once = options.once !== false;
  const path = toShortString(payload.path || window.location.pathname, 320);
  const categorySlug = toShortString(payload.category_slug, 160);
  const dishSlug = toShortString(payload.dish_slug, 210);
  const key = options.onceKey || `${eventType}|${categorySlug}|${dishSlug}|${path}`;
  if (once && seenEventKeys.has(key)) return;
  if (once) seenEventKeys.add(key);

  const body = {
    event_type: eventType,
    path,
    category_slug: categorySlug,
    dish_slug: dishSlug,
    source: toShortString(payload.source || "web", 48),
    session_id: toShortString(payload.session_id || getSessionId(), 64),
    metadata: safeMetadata(payload.metadata || {}),
  };

  api.post("/analytics/events/", body).catch(() => {
    // Ignore telemetry errors to keep core UX uninterrupted.
  });
};
