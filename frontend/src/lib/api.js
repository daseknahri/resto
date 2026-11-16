import axios from "axios";
import {
  isLocalTenantHost,
  isPlatformPublicHost,
} from "./runtimeHost";
import { translate } from "../i18n/translate";
import { shouldRetry, retryBackoffMs } from "./retry";

const runtimeApiBase = () => {
  if (typeof window === "undefined") return "http://localhost:8000/api";
  const protocol = window.location.protocol === "https:" ? "https" : "http";
  const host = window.location.hostname;
  if (isLocalTenantHost(host)) return `${protocol}://${host}:8000/api`;
  return `${protocol}://${host}/api`;
};

export const resolveBaseURL = (envValue) => {
  const runtime = runtimeApiBase();
  if (!envValue || envValue === "auto") return runtime;
  if (typeof window !== "undefined") {
    try {
      const currentHost = window.location.hostname;
      const envHost = new URL(envValue).hostname;
      // In local multi-tenant dev, keep tenant subdomains first-party.
      // But when frontend runs on plain localhost, respect explicit env host.
      if (
        currentHost.endsWith(".localhost") &&
        isLocalTenantHost(envHost) &&
        envHost !== currentHost
      ) {
        return runtime;
      }
      // In production, tenant hosts must stay first-party because backend tenant
      // resolution is driven by the request host. Public/admin hosts can still
      // use explicit API hosts if needed.
      if (
        currentHost &&
        envHost &&
        currentHost !== envHost &&
        !isLocalTenantHost(currentHost) &&
        !isPlatformPublicHost(currentHost)
      ) {
        return runtime;
      }
    } catch {
      // if env isn't a valid absolute URL, fallback to runtime
      return runtime;
    }
  }
  return envValue;
};

const isUnsafeMethod = (method) => ["post", "put", "patch", "delete"].includes(String(method || "").toLowerCase());

// Endpoints whose 401s must NOT trigger the global staff-login redirect. These are
// either the auth flow itself or *customer*-authenticated (IsCustomer) endpoints —
// a stale customer session there must be surfaced by the page (re-open the customer
// sign-in modal), never by bouncing the whole SPA to the STAFF `/signin`.
// `/rides/` is here because CustomerAccount's ride-history fetch (GET /rides/history/)
// is IsCustomer and 401s on expiry like the other `/customer/` reads.
export const AUTH_REDIRECT_EXEMPT_PATHS = [
  "/session/",
  "/signin/",
  "/signout/",
  "/forgot-password/",
  "/reset-password/",
  "/activate/",
  "/customer/",
  "/rides/",
];

export const isAuthRedirectExempt = (url) => {
  const u = String(url || "");
  return AUTH_REDIRECT_EXEMPT_PATHS.some((p) => u.includes(p));
};

// C-06 (Run 8 S2-H): backend `detail` / `non_field_errors` / field-error strings are
// English backend copy and must NEVER reach the customer UI (OPS-6b). The only
// backend-derived message a screen may show is the LOCALIZED string for a known
// backend `code`, looked up here. Anything unmapped falls back to the caller's
// localized fallback — or "" when none is given — never to the raw backend string.
// (The old extractor returned `detail` first; that is the behaviour this replaces.)
//
// Canonical map: backend `code` -> i18n key under the `apiClient` block (EN+FR+AR in
// messages-*.js). Prefix families share one key: every `loyalty_*` code, every
// `schedule_*` code, and every `plan_forbidden*` code.
export const API_ERROR_CODE_MESSAGES = {
  // Checkout / ordering (mirrors Cart's mapOrderApiError code list).
  promo_not_found: "apiClient.promoInvalid",
  promo_invalid: "apiClient.promoInvalid",
  auth_required: "apiClient.authRequired",
  wallet_insufficient: "apiClient.walletInsufficient",
  not_verified: "apiClient.notVerified",
  phone_required: "apiClient.phoneRequired",
  items_unavailable: "apiClient.itemsUnavailable",
  plan_forbidden: "apiClient.planForbidden",
  plan_forbidden_checkout: "apiClient.planForbidden",
  menu_unpublished: "apiClient.menuUnpublished",
  restaurant_closed: "apiClient.restaurantClosed",
  contact_missing: "apiClient.contactMissing",
  table_unavailable: "apiClient.tableUnavailable",
  mixed_currency: "apiClient.mixedCurrency",
  stale_options: "apiClient.staleOptions",
  menu_temporarily_disabled: "apiClient.menuTemporarilyDisabled",
  below_delivery_minimum: "apiClient.belowDeliveryMinimum",
  delivery_out_of_range: "apiClient.deliveryOutOfRange",
  ordering_paused: "apiClient.orderingPaused",
  dine_in_unavailable: "apiClient.dineInUnavailable",
  delivery_unavailable: "apiClient.deliveryUnavailable",
  schedule_invalid: "apiClient.scheduleInvalid",
  currency_unsupported: "apiClient.currencyUnsupported",
  loyalty_insufficient_points: "apiClient.loyaltyError",
  // Customer auth / account (accounts/views.py error codes).
  otp_expired: "apiClient.otpExpired",
  too_many_attempts: "apiClient.tooManyAttempts",
  invalid_code: "apiClient.invalidCode",
  otp_rate_limited: "apiClient.otpRateLimited",
  otp_cooldown: "apiClient.otpCooldown",
  invalid_phone: "apiClient.invalidPhone",
  phone_taken: "apiClient.phoneTaken",
  email_taken: "apiClient.emailTaken",
  email_invalid: "apiClient.emailInvalid",
  email_required: "apiClient.emailRequired",
  name_required: "apiClient.nameRequired",
  phone_unverified: "apiClient.phoneUnverified",
  invalid_credential: "apiClient.invalidCredential",
  not_configured: "apiClient.notConfigured",
  password_too_weak: "apiClient.passwordTooWeak",
  wrong_current_password: "apiClient.wrongCurrentPassword",
  current_password_required: "apiClient.currentPasswordRequired",
  new_password_required: "apiClient.newPasswordRequired",
  // Generic / shared.
  rate_limited: "apiClient.rateLimited",
  not_found: "apiClient.notFound",
  forbidden: "apiClient.forbidden",
  invalid: "apiClient.invalidRequest",
  invalid_body: "apiClient.invalidRequest",
  server_error: "apiClient.serverError",
  unavailable: "apiClient.unavailable",
  already_claimed: "apiClient.alreadyClaimed",
  phone_mismatch: "apiClient.phoneMismatch",
  voucher_locked: "apiClient.voucherLocked",
  already_used: "apiClient.alreadyUsed",
  already_revoked: "apiClient.alreadyRevoked",
  insufficient: "apiClient.insufficientBalance",
  expired: "apiClient.expired",
  conflict: "apiClient.conflict",
  cancel_too_late: "apiClient.cancelTooLate",
  not_owner: "apiClient.notOwner",
  missing_fields: "apiClient.missingFields",
  staff_session_conflict: "apiClient.sessionConflict",
  no_tenant: "apiClient.noTenant",
};

// Prefix families: one localized key per family (see map above).
const API_ERROR_CODE_PREFIXES = [
  ["loyalty_", "apiClient.loyaltyError"],
  ["schedule_", "apiClient.scheduleInvalid"],
  ["plan_forbidden", "apiClient.planForbidden"],
];

// Resolve a backend error `code` to its i18n key, or "" when the code is unknown.
// Shared by stores/menu.js so both extractors map codes identically.
export const mapApiErrorCode = (code) => {
  if (typeof code !== "string" || !code) return "";
  if (Object.prototype.hasOwnProperty.call(API_ERROR_CODE_MESSAGES, code)) return API_ERROR_CODE_MESSAGES[code];
  const prefix = API_ERROR_CODE_PREFIXES.find(([p]) => code.startsWith(p));
  return prefix ? prefix[1] : "";
};

// Canonical extractor for a human message out of an axios/DRF error. Single source of
// truth. Contract (C-06): a known `data.code` returns its LOCALIZED message; anything
// else returns the caller's localized `fallback` ("" when none is given). Raw backend
// strings (`detail`, `non_field_errors`, field errors, bare-list bodies, plain-string
// bodies) are NEVER returned.
export const extractApiErrorMessage = (err, fallback = "") => {
  const key = mapApiErrorCode(err?.response?.data?.code);
  if (key) return translate(key);
  return fallback;
};

const readCookie = (name) => {
  if (typeof document === "undefined") return "";
  const prefix = `${name}=`;
  const entry = document.cookie.split("; ").find((row) => row.startsWith(prefix));
  return entry ? decodeURIComponent(entry.slice(prefix.length)) : "";
};

const isCsrfMismatchError = (error) => {
  if (error?.response?.status !== 403) return false;
  const body = error?.response?.data;
  if (typeof body === "string") return body.toLowerCase().includes("csrf");
  const detail = String(body?.detail || "").toLowerCase();
  return detail.includes("csrf");
};

const stripCsrfHeaders = (headers) => {
  if (!headers || typeof headers !== "object") return;
  delete headers["X-CSRFToken"];
  delete headers["X-Csrftoken"];
  delete headers["x-csrftoken"];
};

const readRuntimeLocale = () => {
  if (typeof document === "undefined") return "";
  const fromDocument = String(document.documentElement?.lang || "").trim().toLowerCase();
  if (fromDocument) return fromDocument;
  if (typeof window !== "undefined") {
    try {
      const host = window.location.hostname || "default";
      const scoped = String(window.localStorage.getItem(`resto.locale:${host}`) || "").trim().toLowerCase();
      if (scoped) return scoped;
      return String(window.localStorage.getItem("resto.locale") || "").trim().toLowerCase();
    } catch {
      return "";
    }
  }
  return "";
};

// Shared request-header logic (locale header/param + CSRF token on unsafe methods).
const applyRequestHeaders = (config) => {
  const method = (config.method || "get").toLowerCase();
  const locale = readRuntimeLocale();
  if (locale) {
    config.headers = config.headers || {};
    config.headers["Accept-Language"] = locale;
    if (["get", "head", "options"].includes(method)) {
      config.params = config.params || {};
      if (!config.params.lang) {
        config.params.lang = locale;
      }
    }
  }
  if (isUnsafeMethod(method)) {
    config.headers = config.headers || {};
    if (!config.headers["X-CSRFToken"] && !config.headers["X-Csrftoken"] && !config.headers["x-csrftoken"]) {
      const token = readCookie("csrftoken");
      if (token) config.headers["X-CSRFToken"] = token;
    }
  }
  return config;
};

// Single axios-client factory so every client (the tenant `api` and the platform-admin
// `adminApi`) gets the SAME request + response behavior: locale/CSRF request headers,
// transient-5xx/network retry, CSRF-mismatch re-fetch-and-retry, the global staff
// 401 → /signin redirect, and the friendly 429 message. (adminApi used to hand-roll a
// copy that silently dropped retry / 401-redirect / 429, so every admin call lost them.)
export function createApiClient({ baseURL, timeout = 30000 }) {
  const client = axios.create({
    baseURL,
    withCredentials: true,
    xsrfCookieName: "csrftoken",
    xsrfHeaderName: "X-CSRFToken",
    timeout,
  });

  const refreshCsrfCookie = async () => {
    const locale = readRuntimeLocale();
    const config = { withCredentials: true, headers: {}, params: {} };
    if (locale) {
      config.headers["Accept-Language"] = locale;
      config.params.lang = locale;
    }
    await client.get("/session/", config);
  };

  client.interceptors.request.use(applyRequestHeaders);

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const original = error?.config || {};
      // Retry transient network/5xx failures on idempotent requests (flaky WiFi).
      original.__retryCount = original.__retryCount || 0;
      if (shouldRetry(error, original.__retryCount)) {
        original.__retryCount += 1;
        const jitter = Math.random() * 150;
        await new Promise((resolve) => setTimeout(resolve, retryBackoffMs(original.__retryCount - 1, jitter)));
        return client.request(original);
      }
      if (isCsrfMismatchError(error) && isUnsafeMethod(original.method) && !original.__csrfRetried) {
        original.__csrfRetried = true;
        original.headers = { ...(original.headers || {}) };
        stripCsrfHeaders(original.headers);
        try {
          await refreshCsrfCookie();
          return client.request(original);
        } catch {
          // If refresh fails, keep original error.
        }
      }
      if (error?.response?.status === 401 && typeof window !== "undefined") {
        const isAuthEndpoint = isAuthRedirectExempt(error?.config?.url);
        if (!isAuthEndpoint) {
          const next = encodeURIComponent(window.location.pathname + window.location.search);
          // `expired=1` lets SignIn.vue show "session expired" instead of the generic description
          window.location.href = `/signin?next=${next}&expired=1`;
          // Return a never-resolving promise so callers don't see a spurious rejection
          return new Promise(() => {});
        }
      }
      if (error.response?.status === 429) {
        // Tag the rewritten body with the code so the C-06 extractor can map it to
        // the localized rate-limit message instead of dropping it to the fallback.
        error.response.data = { code: "rate_limited", detail: translate("apiClient.rateLimitRetry") };
      }
      return Promise.reject(error);
    }
  );

  return client;
}

const api = createApiClient({
  baseURL: resolveBaseURL(import.meta.env.VITE_API_BASE_URL),
  timeout: 30000,
});

export default api;
