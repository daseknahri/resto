const parseCsv = (value) =>
  String(value || "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

export const isLocalTenantHost = (host) => host === "localhost" || host.endsWith(".localhost");

const platformPublicHosts = parseCsv(import.meta.env.VITE_PLATFORM_PUBLIC_HOSTS || "");

const firstMatchingHost = (matcher) => platformPublicHosts.find((host) => matcher(host)) || "";

export const currentHostname = () => {
  if (typeof window === "undefined") return "";
  return String(window.location.hostname || "").trim().toLowerCase();
};

export const isPlatformPublicHost = (host = currentHostname()) => {
  const normalized = String(host || "").trim().toLowerCase();
  return platformPublicHosts.includes(normalized);
};

export const isPlatformAdminHost = (host = currentHostname()) => {
  const normalized = String(host || "").trim().toLowerCase();
  return normalized === "admin" || normalized.startsWith("admin.");
};

export const isPlatformApiHost = (host = currentHostname()) => {
  const normalized = String(host || "").trim().toLowerCase();
  return normalized === "api" || normalized.startsWith("api.");
};

export const isPublicDemoHost = (host = currentHostname()) =>
  isPlatformPublicHost(host) && !isPlatformAdminHost(host) && !isPlatformApiHost(host);

export const getPlatformAdminHost = () => firstMatchingHost((host) => isPlatformAdminHost(host));

export const getPrimaryPublicHost = () =>
  firstMatchingHost((host) => !isPlatformAdminHost(host) && !isPlatformApiHost(host));
