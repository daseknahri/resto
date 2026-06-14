import { watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "./useI18n";
import { useTenantStore } from "../stores/tenant";
import { isPlatformAdminHost, isPlatformApiHost } from "../lib/runtimeHost";
import { PLATFORM_NAME } from "../lib/brand";

// schema.org @type per business vertical (mirrors tenant store businessType
// values: restaurant | cafe | bakery | grocery | retail | pharmacy).
const BUSINESS_TYPE_SCHEMA_MAP = {
  restaurant: "Restaurant",
  cafe: "CafeOrCoffeeShop",
  bakery: "Bakery",
  grocery: "GroceryStore",
  retail: "Store",
  pharmacy: "Pharmacy",
};

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
  // ── Customer routes ────────────────────────────────────────────────────────
  if (name === "customer-home") return t("customerLayout.navInfo");
  if (name === "menu" || name === "category" || name === "dish" || name === "table-link") return t("customerLayout.navMenu");
  if (name === "cart") return t("customerLayout.navCart");
  if (name === "reserve") return t("customerLayout.navReserve");
  if (name === "customer-account") return t("customerLayout.navAccount");
  if (name === "find-my-order") return t("customerLayout.findMyOrder");
  if (name === "order-status") return t("orderStatus.title");
  // ── Owner routes ───────────────────────────────────────────────────────────
  if (name === "owner-home" || name === "owner-menu-builder") return t("ownerLayout.dashboard");
  if (name === "owner-orders") return t("ownerLayout.orders");
  if (name === "owner-reservations") return t("ownerLayout.reservations");
  if (name === "owner-tables") return t("ownerLayout.tablesQr");
  if (name === "owner-kitchen") return t("ownerLayout.kitchen");
  if (name === "owner-staff") return t("ownerLayout.staff");
  if (name === "owner-ratings") return t("ownerLayout.ratings");
  if (name === "owner-promotions") return t("ownerLayout.promotions");
  if (name === "owner-loyalty") return t("ownerLayout.loyalty");
  if (name === "owner-wallet") return t("ownerLayout.wallet");
  if (name === "owner-profile") return t("ownerLayout.profile");
  if (name === "owner-billing") return t("ownerLayout.billing");
  if (name === "owner-launch") return t("ownerLayout.kicker");
  if (name.startsWith("owner")) return t("ownerLayout.kicker");
  // ── Waiter routes ──────────────────────────────────────────────────────────
  if (name === "waiter") return t("waiterLayout.role");
  // ── Admin routes ───────────────────────────────────────────────────────────
  if (name === "admin-console") return "Admin Console";
  if (name === "admin-delivery-zones") return "Delivery Zones";
  if (name === "admin-drivers") return "Drivers";
  if (name === "admin-analytics") return "Analytics";
  if (name === "admin-wallets") return "Wallets";
  // ── Auth / misc ────────────────────────────────────────────────────────────
  if (name === "signin") return t("common.signIn");
  if (name === "forgot-password") return t("forgotPassword.title");
  if (name === "activate") return t("activateAccount.title");
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
      upsertMeta({ key: "og:site_name", value: PLATFORM_NAME, attr: "property" });
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
      const businessType = String(profile.business_type || "").trim().toLowerCase();
      const schemaType = BUSINESS_TYPE_SCHEMA_MAP[businessType] || "Restaurant";
      const ld = {
        "@context": "https://schema.org",
        "@type": schemaType,
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
