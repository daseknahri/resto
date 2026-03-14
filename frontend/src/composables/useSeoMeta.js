import { watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "./useI18n";
import { useTenantStore } from "../stores/tenant";
import { isPlatformAdminHost, isPlatformApiHost } from "../lib/runtimeHost";

const setDocumentTitle = (value) => {
  if (typeof document === "undefined") return;
  document.title = String(value || "").trim();
};

const upsertMeta = ({ key, value, attr = "name" }) => {
  if (typeof document === "undefined") return;
  const normalizedKey = String(key || "").trim();
  if (!normalizedKey) return;
  let node = document.head.querySelector(`meta[${attr}="${normalizedKey}"]`);
  if (!value) {
    if (node) node.remove();
    return;
  }
  if (!node) {
    node = document.createElement("meta");
    node.setAttribute(attr, normalizedKey);
    document.head.appendChild(node);
  }
  node.setAttribute("content", String(value));
};

const upsertLink = ({ rel, href }) => {
  if (typeof document === "undefined") return;
  const normalizedRel = String(rel || "").trim();
  if (!normalizedRel) return;
  let node = document.head.querySelector(`link[rel="${normalizedRel}"]`);
  if (!href) {
    if (node) node.remove();
    return;
  }
  if (!node) {
    node = document.createElement("link");
    node.setAttribute("rel", normalizedRel);
    document.head.appendChild(node);
  }
  node.setAttribute("href", String(href));
};

const upsertJsonLd = (id, payload) => {
  if (typeof document === "undefined") return;
  const normalizedId = String(id || "").trim();
  if (!normalizedId) return;
  let node = document.getElementById(normalizedId);
  if (!payload) {
    if (node) node.remove();
    return;
  }
  const nextContent = JSON.stringify(payload);
  if (!node) {
    node = document.createElement("script");
    node.id = normalizedId;
    node.type = "application/ld+json";
    document.head.appendChild(node);
  }
  if (node.textContent !== nextContent) {
    node.textContent = nextContent;
  }
};

const normalizeUrl = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    return new URL(raw).toString();
  } catch {
    return "";
  }
};

const sanitizePhone = (value) => String(value || "").replace(/[^\d+]/g, "");

const localeToOgLocale = (locale) => {
  const normalized = String(locale || "").toLowerCase();
  if (normalized === "fr") return "fr_FR";
  if (normalized === "ar") return "ar_MA";
  return "en_US";
};

const routeTitleLabel = (route, t) => {
  const name = String(route?.name || "");
  if (name === "customer-home") return t("customerLayout.navInfo");
  if (name === "menu" || name === "category" || name === "dish" || name === "table-link") return t("customerLayout.navMenu");
  if (name === "cart") return t("customerLayout.navCart");
  if (name === "reserve") return t("customerLayout.navReserve");
  if (name.startsWith("owner")) return "Owner workspace";
  if (name === "admin-console") return "Admin console";
  if (name === "signin") return "Sign in";
  return "Menu";
};

const isCustomerRoute = (route) =>
  Array.isArray(route?.matched) && route.matched.some((record) => record?.meta?.interface === "customer");

const isLandingRoute = (route) =>
  Array.isArray(route?.matched) && route.matched.some((record) => record?.meta?.interface === "landing");

export const useSeoMeta = () => {
  const route = useRoute();
  const tenant = useTenantStore();
  const { currentLocale, t } = useI18n();

  watch(
    [
      () => route.fullPath,
      () => route.name,
      () => route.path,
      () => route.matched.map((m) => m.meta?.interface).join("|"),
      () => tenant.resolvedMeta,
      () => currentLocale.value,
    ],
    () => {
      if (typeof window === "undefined") return;

      const origin = window.location.origin;
      const canonical = `${origin}${route.path || "/"}`;
      const locale = String(currentLocale.value || "en");
      const ogLocale = localeToOgLocale(locale);
      const tenantMeta = tenant.resolvedMeta || null;
      const profile = tenantMeta?.profile || {};
      const tenantName = String(tenantMeta?.name || t("customerLayout.fallbackTenantName")).trim();
      const description =
        String(profile.description || "").trim() ||
        String(profile.tagline || "").trim() ||
        t("customerLeadPage.fallbackDescription");
      const logoUrl = normalizeUrl(profile.logo_url);
      const heroUrl = normalizeUrl(profile.hero_url);
      const pageLabel = routeTitleLabel(route, t);
      const title = `${tenantName} | ${pageLabel}`;
      const image = heroUrl || logoUrl;

      const adminHost = isPlatformAdminHost();
      const apiHost = isPlatformApiHost();
      const customer = isCustomerRoute(route);
      const landing = isLandingRoute(route);
      const shouldIndex = (customer || landing) && !adminHost && !apiHost;

      setDocumentTitle(title);
      upsertMeta({ key: "description", value: description, attr: "name" });
      upsertMeta({ key: "robots", value: shouldIndex ? "index,follow" : "noindex,nofollow", attr: "name" });
      upsertLink({ rel: "canonical", href: canonical });

      upsertMeta({ key: "og:type", value: "website", attr: "property" });
      upsertMeta({ key: "og:site_name", value: tenantName, attr: "property" });
      upsertMeta({ key: "og:title", value: title, attr: "property" });
      upsertMeta({ key: "og:description", value: description, attr: "property" });
      upsertMeta({ key: "og:url", value: canonical, attr: "property" });
      upsertMeta({ key: "og:locale", value: ogLocale, attr: "property" });
      upsertMeta({ key: "og:image", value: image || "", attr: "property" });

      upsertMeta({ key: "twitter:card", value: image ? "summary_large_image" : "summary", attr: "name" });
      upsertMeta({ key: "twitter:title", value: title, attr: "name" });
      upsertMeta({ key: "twitter:description", value: description, attr: "name" });
      upsertMeta({ key: "twitter:image", value: image || "", attr: "name" });

      if (!customer || !tenantMeta || adminHost || apiHost) {
        upsertJsonLd("tenant-restaurant-jsonld", null);
        return;
      }

      const sameAs = [
        normalizeUrl(profile.instagram_url),
        normalizeUrl(profile.facebook_url),
        normalizeUrl(profile.tiktok_url),
        normalizeUrl(profile.google_maps_url),
      ].filter(Boolean);

      const addressLine = String(profile.address || "").trim();
      const city = String(profile.city || "").trim();
      const phone = sanitizePhone(profile.phone || profile.whatsapp);
      const restaurantUrl = `${origin}/menu`;
      const ld = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        name: tenantName,
        description,
        url: restaurantUrl,
        inLanguage: locale,
        ...(image ? { image: [image] } : {}),
        ...(phone ? { telephone: phone } : {}),
        ...(sameAs.length ? { sameAs } : {}),
        ...(addressLine || city
          ? {
              address: {
                "@type": "PostalAddress",
                ...(addressLine ? { streetAddress: addressLine } : {}),
                ...(city ? { addressLocality: city } : {}),
                addressCountry: "MA",
              },
            }
          : {}),
      };
      upsertJsonLd("tenant-restaurant-jsonld", ld);
    },
    { immediate: true }
  );
};
