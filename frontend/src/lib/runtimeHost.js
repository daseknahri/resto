const parseCsv = (value) =>
  String(value || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

export const isLocalTenantHost = (host) => host === "localhost" || host.endsWith(".localhost");

const platformPublicHosts = parseCsv(import.meta.env.VITE_PLATFORM_PUBLIC_HOSTS || "");
const publicDemoTenantSlug = String(import.meta.env.VITE_PUBLIC_DEMO_TENANT_SLUG || "")
  .trim()
  .toLowerCase();

const isLikelyMenuRootHost = (host) => {
  const normalized = String(host || "").trim().toLowerCase();
  return normalized === "menu" || normalized.startsWith("menu.");
};

const isLikelyAdminRootHost = (host) => {
  const normalized = String(host || "").trim().toLowerCase();
  return normalized === "admin" || normalized.startsWith("admin.");
};

const isLikelyApiRootHost = (host) => {
  const normalized = String(host || "").trim().toLowerCase();
  return normalized === "api" || normalized.startsWith("api.");
};

const firstMatchingHost = (matcher) => platformPublicHosts.find((host) => matcher(host)) || "";

export const currentHostname = () => {
  if (typeof window === "undefined") return "";
  return String(window.location.hostname || "").trim().toLowerCase();
};

export const isPlatformPublicHost = (host = currentHostname()) => {
  const normalized = String(host || "").trim().toLowerCase();
  if (platformPublicHosts.includes(normalized)) return true;
  // Fallback for production builds where VITE_PLATFORM_PUBLIC_HOSTS might be missing.
  // This keeps root hosts (menu/admin/api) from being treated as tenant hosts.
  return (
    isLikelyMenuRootHost(normalized) ||
    isLikelyAdminRootHost(normalized) ||
    isLikelyApiRootHost(normalized)
  );
};

export const isPlatformAdminHost = (host = currentHostname()) => {
  const normalized = String(host || "").trim().toLowerCase();
  return isLikelyAdminRootHost(normalized);
};

export const isPlatformApiHost = (host = currentHostname()) => {
  const normalized = String(host || "").trim().toLowerCase();
  return isLikelyApiRootHost(normalized);
};

export const isPublicDemoHost = (host = currentHostname()) =>
  isPlatformPublicHost(host) && !isPlatformAdminHost(host) && !isPlatformApiHost(host);

export const getPlatformAdminHost = () => firstMatchingHost((host) => isPlatformAdminHost(host));

export const getPrimaryPublicHost = () =>
  firstMatchingHost((host) => !isPlatformAdminHost(host) && !isPlatformApiHost(host));

export const getPublicDemoTenantSlug = () => publicDemoTenantSlug;

export const hasPublicDemoTenant = () => Boolean(publicDemoTenantSlug);
