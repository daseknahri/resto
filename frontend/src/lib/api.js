import axios from "axios";

const isLocalTenantHost = (host) => host === "localhost" || host.endsWith(".localhost");

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
      // In local multi-tenant dev, keep tenant subdomains first-party.
      // But when frontend runs on plain localhost, respect explicit env host.
      if (
        currentHost.endsWith(".localhost") &&
        isLocalTenantHost(envHost) &&
        envHost !== currentHost
      ) {
        return runtime;
      }
    } catch (e) {
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

const readCookie = (name) => {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
};

api.interceptors.request.use((config) => {
  const method = (config.method || "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const token = readCookie("csrftoken");
    if (token) {
      config.headers = config.headers || {};
      config.headers["X-CSRFToken"] = token;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 429) {
      error.response.data = { detail: "Rate limit hit. Please retry shortly." };
    }
    return Promise.reject(error);
  }
);

export default api;
