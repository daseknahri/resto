import { createApiClient, resolveBaseURL } from "./api";

// Platform-admin client. Uses the SHARED createApiClient factory so it gets the same
// request/response behavior as the tenant `api` — crucially the transient-5xx/network
// retry, the global staff 401 → /signin redirect, and the friendly 429 message, which
// the previous hand-rolled copy silently dropped (every admin-console call lost them).
// Only the base URL (admin env override) and the shorter timeout differ.
const adminApi = createApiClient({
  baseURL: resolveBaseURL(import.meta.env.VITE_ADMIN_API_BASE_URL || import.meta.env.VITE_API_BASE_URL),
  timeout: 15000,
});

export default adminApi;
