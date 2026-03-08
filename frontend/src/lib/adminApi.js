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
      if (
        currentHost.endsWith(".localhost") &&
        isLocalTenantHost(envHost) &&
        envHost !== currentHost
      ) {
        return runtime;
      }
    } catch (e) {
      return runtime;
    }
  }
  return envValue;
};

const adminApi = axios.create({
  baseURL: resolveBaseURL(import.meta.env.VITE_ADMIN_API_BASE_URL || import.meta.env.VITE_API_BASE_URL),
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFToken",
});

const readCookie = (name) => {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : "";
};

adminApi.interceptors.request.use((config) => {
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

export default adminApi;
