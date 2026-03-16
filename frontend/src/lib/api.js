import axios from "axios";
import {
  getPublicDemoTenantSlug,
  hasPublicDemoTenant,
  isLocalTenantHost,
  isPlatformPublicHost,
  isPublicDemoHost,
} from "./runtimeHost";
import { translate } from "../i18n/translate";

const runtimeApiBase = () => {
  if (typeof window === "undefined") return "http://localhost:8000/api";
  const protocol = window.location.protocol === "https:" ? "https" : "http";
  const host = window.location.hostname;
  if (isPublicDemoHost(host) && hasPublicDemoTenant()) {
    return `${protocol}://${getPublicDemoTenantSlug()}.${host}/api`;
  }
  if (isLocalTenantHost(host)) return `${protocol}://${host}:8000/api`;
  return `${protocol}://${host}/api`;
};

const resolveBaseURL = (envValue) => {
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

const api = axios.create({
  baseURL: resolveBaseURL(import.meta.env.VITE_API_BASE_URL),
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFToken",
});

const isUnsafeMethod = (method) => ["post", "put", "patch", "delete"].includes(String(method || "").toLowerCase());

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

const refreshCsrfCookie = async () => {
  const locale = readRuntimeLocale();
  const config = {
    withCredentials: true,
    headers: {},
    params: {},
  };
  if (locale) {
    config.headers["Accept-Language"] = locale;
    config.params.lang = locale;
  }
  await api.get("/session/", config);
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

api.interceptors.request.use((config) => {
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
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error?.config || {};
    if (isCsrfMismatchError(error) && isUnsafeMethod(original.method) && !original.__csrfRetried) {
      original.__csrfRetried = true;
      original.headers = { ...(original.headers || {}) };
      stripCsrfHeaders(original.headers);
      try {
        await refreshCsrfCookie();
        return api.request(original);
      } catch {
        // If refresh fails, keep original error.
      }
    }
    if (error.response?.status === 429) {
      error.response.data = { detail: translate("apiClient.rateLimitRetry") };
    }
    return Promise.reject(error);
  }
);

export default api;
