import axios from "axios";
import { isLocalTenantHost, isPlatformPublicHost } from "./runtimeHost";

const runtimeApiBase = () => {
  if (typeof window === "undefined") return "http://localhost:8000/api";
  const protocol = window.location.protocol === "https:" ? "https" : "http";
  const host = window.location.hostname;
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
      if (
        currentHost.endsWith(".localhost") &&
        isLocalTenantHost(envHost) &&
        envHost !== currentHost
      ) {
        return runtime;
      }
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
      return runtime;
    }
  }
  return envValue;
};

const adminApi = axios.create({
  baseURL: resolveBaseURL(import.meta.env.VITE_ADMIN_API_BASE_URL || import.meta.env.VITE_API_BASE_URL),
  timeout: 15000,
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFToken",
});

const isUnsafeMethod = (method) => ["post", "put", "patch", "delete"].includes(String(method || "").toLowerCase());

const readCookie = (name) => {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(?:^|; )${name.replace(/([.$?*|{}()\\[\\]\\/\\+^])/g, "\\$1")}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
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
  await adminApi.get("/session/", config);
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

adminApi.interceptors.request.use((config) => {
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

adminApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error?.config || {};
    if (isCsrfMismatchError(error) && isUnsafeMethod(original.method) && !original.__csrfRetried) {
      original.__csrfRetried = true;
      original.headers = { ...(original.headers || {}) };
      stripCsrfHeaders(original.headers);
      try {
        await refreshCsrfCookie();
        return adminApi.request(original);
      } catch {
        // Keep original error if refresh/retry fails.
      }
    }
    return Promise.reject(error);
  }
);

export default adminApi;
