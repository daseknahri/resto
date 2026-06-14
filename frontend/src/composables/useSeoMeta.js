import { watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "./useI18n";
import { useTenantStore } from "../stores/tenant";
import { useMenuStore } from "../stores/menu";
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

// Canonical currency for all stored prices (see stores/currency.js BASE_CODE).
// JSON-LD offers advertise the canonical price, not the visitor's display pick.
const PRICE_CURRENCY = "MAD";

// Locales the storefront serves, mirrored for hreflang alternates. Keep in sync
// with i18n/config.js LOCALE_OPTIONS.
const HREFLANG_LOCALES = ["en", "fr", "ar"];

// Routes that are genuinely PUBLIC discovery surfaces and safe to index. Every
// other customer/landing route (cart, account, order status, find-my-order,
// checkout, reservation forms, ride/package flows, marketplace order status …)
// is personal/transactional and must stay out of the index, matching
// robots.txt Disallow rules. Allowlist > denylist: a new private route is
// noindex by default until it is explicitly added here.
const INDEXABLE_ROUTE_NAMES = new Set([
  // Landing discovery
  "home",
  "demo",
  "directory",
  "marketplace",
  "marketplace-menu",
  // Public marketing pages (linked from footer; also listed in the sitemap).
  // /reserve is intentionally NOT here — it is a personal/transactional form.
  "privacy",
  "terms",
  "contact",
  // Customer storefront discovery
  "customer-home",
  "menu",
  "menu-browse",
  // NOTE: table-link (/t/:tableSlug) is deliberately NOT indexable — every physical
  // table's QR deep-link renders the same menu, so indexing them creates near-duplicate
  // URLs that dilute crawl budget. The canonical menu/category/dish routes cover discovery.
  "category",
  "dish",
]);

// Routes that show a single menu item and can carry a Product/MenuItem offer +
// BreadcrumbList. Maps to the menu store shape (category slug → dishes).
const ITEM_ROUTE_NAMES = new Set(["dish"]);
const BREADCRUMB_ROUTE_NAMES = new Set(["menu", "menu-browse", "category", "dish"]);

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

const upsertLink = ({ rel, href, attrs = {} }) => {
  if (typeof document === "undefined") return;
  const normalizedRel = String(rel || "").trim();
  if (!normalizedRel) return;
  // hreflang variants share rel="alternate" but differ by hreflang, so the
  // selector keys on every disambiguating attribute, not rel alone.
  const attrSelector = Object.entries(attrs)
    .map(([name, val]) => `[${name}="${String(val).replace(/"/g, '\\"')}"]`)
    .join("");
  const selector = `link[rel="${normalizedRel}"]${attrSelector}`;
  let node = document.head.querySelector(selector);
  if (!href) {
    if (node) node.remove();
    return;
  }
  if (!node) {
    node = document.createElement("link");
    node.setAttribute("rel", normalizedRel);
    Object.entries(attrs).forEach(([name, val]) => node.setAttribute(name, String(val)));
    document.head.appendChild(node);
  }
  node.setAttribute("href", String(href));
};

// Remove every hreflang alternate (used when a page is not indexable so stale
// alternates from a prior navigation never linger).
const clearHreflangLinks = () => {
  if (typeof document === "undefined") return;
  document.head
    .querySelectorAll('link[rel="alternate"][hreflang]')
    .forEach((node) => node.remove());
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

// Build the same path with an explicit ?lang= override so each hreflang
// alternate points at the localized variant. Mirrors how the locale is keyed
// (?lang query is honored as a one-shot override at boot / by the switcher).
const buildLocaleUrl = (origin, path, query, locale) => {
  const params = new URLSearchParams(query || {});
  params.set("lang", locale);
  const qs = params.toString();
  return `${origin}${path || "/"}${qs ? `?${qs}` : ""}`;
};

const routeTitleLabel = (route, t) => {
  const name = String(route?.name || "");
  // ── Customer routes ────────────────────────────────────────────────────────
  if (name === "customer-home") return t("customerLayout.navInfo");
  if (name === "menu" || name === "menu-browse" || name === "category" || name === "dish" || name === "table-link") return t("customerLayout.navMenu");
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

// schema.org day map for openingHoursSpecification (mirrors the mon/tue… keys in
// Profile.business_hours_schedule).
const SCHEMA_WEEKDAY = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
  sun: "Sunday",
};

const buildOpeningHours = (schedule) => {
  if (!schedule || typeof schedule !== "object") return [];
  const specs = [];
  Object.entries(schedule).forEach(([day, entry]) => {
    const dayName = SCHEMA_WEEKDAY[day];
    if (!dayName || !entry || typeof entry !== "object") return;
    if (entry.enabled !== true) return;
    const opens = String(entry.open || "").trim();
    const closes = String(entry.close || "").trim();
    if (!opens || !closes) return;
    specs.push({
      "@type": "OpeningHoursSpecification",
      dayOfWeek: `https://schema.org/${dayName}`,
      opens,
      closes,
    });
  });
  return specs;
};

// Map the profile price_tier (1–4 or "$".."$$$$") to a schema.org priceRange.
const buildPriceRange = (priceTier) => {
  const raw = String(priceTier ?? "").trim();
  if (!raw) return "";
  if (/^\$+$/.test(raw)) return raw;
  const n = Number(raw);
  if (Number.isInteger(n) && n >= 1 && n <= 4) return "$".repeat(n);
  return "";
};

export const useSeoMeta = () => {
  const route = useRoute();
  const router = useRouter();
  const tenant = useTenantStore();
  const menu = useMenuStore();
  const { currentLocale, t } = useI18n();

  watch(
    [
      () => route.fullPath,
      () => route.name,
      () => route.path,
      () => route.matched.map((m) => m.meta?.interface).join("|"),
      () => tenant.resolvedMeta,
      () => currentLocale.value,
      // Item-level JSON-LD depends on the loaded menu, which arrives async.
      () => menu.categories.length,
      () => Object.keys(menu.dishes).length,
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
      const routeName = String(route.name || "");
      // Only genuinely public discovery routes are indexable. Personal /
      // transactional routes (cart, account, order-status, find-my-order,
      // checkout, reservation forms, ride/package …) emit noindex,nofollow so
      // personalized order data never leaks into search indexes.
      const shouldIndex =
        INDEXABLE_ROUTE_NAMES.has(routeName) && !adminHost && !apiHost;

      setDocumentTitle(title);
      upsertMeta({ key: "description", value: description, attr: "name" });
      upsertMeta({ key: "robots", value: shouldIndex ? "index,follow" : "noindex,nofollow", attr: "name" });
      upsertLink({ rel: "canonical", href: canonical });

      // ── hreflang alternates ──────────────────────────────────────────────────
      // Emit reciprocal language alternates (+ x-default) only for indexable
      // pages, so Google associates the en/fr/ar variants. Always clear first so
      // navigating from an indexable to a private route drops stale tags.
      clearHreflangLinks();
      if (shouldIndex) {
        HREFLANG_LOCALES.forEach((lng) => {
          upsertLink({
            rel: "alternate",
            href: buildLocaleUrl(origin, route.path, route.query, lng),
            attrs: { hreflang: lng },
          });
        });
        upsertLink({
          rel: "alternate",
          href: buildLocaleUrl(origin, route.path, route.query, HREFLANG_LOCALES[0]),
          attrs: { hreflang: "x-default" },
        });
      }

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
        upsertJsonLd("tenant-breadcrumb-jsonld", null);
        upsertJsonLd("tenant-menuitem-jsonld", null);
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
      const menuUrl = `${origin}/menu`;
      const businessType = String(profile.business_type || "").trim().toLowerCase();
      const schemaType = BUSINESS_TYPE_SCHEMA_MAP[businessType] || "Restaurant";

      // ── Enrichment from profile (only when present) ──────────────────────────
      const openingHours = buildOpeningHours(profile.business_hours_schedule);
      const priceRange = buildPriceRange(profile.price_tier);
      const lat = Number(profile.lat);
      const lng = Number(profile.lng);
      const hasGeo = Number.isFinite(lat) && Number.isFinite(lng) && (lat !== 0 || lng !== 0);
      const cuisine = String(profile.cuisine_type || "").trim();
      const ratingSummary = tenantMeta.rating_summary || {};
      const ratingAvg = Number(ratingSummary.average);
      const ratingCount = Number(ratingSummary.count);
      const hasRating = Number.isFinite(ratingAvg) && Number.isFinite(ratingCount) && ratingCount > 0;

      const ld = {
        "@context": "https://schema.org",
        "@type": schemaType,
        "@id": `${origin}/#business`,
        name: tenantName,
        description,
        url: menuUrl,
        inLanguage: locale,
        ...(image ? { image: [image] } : {}),
        ...(phone ? { telephone: phone } : {}),
        ...(sameAs.length ? { sameAs } : {}),
        ...(priceRange ? { priceRange } : {}),
        ...(cuisine ? { servesCuisine: cuisine } : {}),
        ...(openingHours.length ? { openingHoursSpecification: openingHours } : {}),
        ...(hasGeo ? { geo: { "@type": "GeoCoordinates", latitude: lat, longitude: lng } } : {}),
        ...(hasRating
          ? {
              aggregateRating: {
                "@type": "AggregateRating",
                ratingValue: ratingAvg,
                reviewCount: ratingCount,
              },
            }
          : {}),
        hasMenu: menuUrl,
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

      // ── BreadcrumbList on menu/category/dish pages ───────────────────────────
      if (BREADCRUMB_ROUTE_NAMES.has(routeName)) {
        // Resolve crumb URLs from their semantic named routes so the path
        // always matches the label: "Home" → the customer storefront landing
        // (route customer-home, /menu), "Menu" → the menu hub (route menu, /browse).
        const homePath = router.resolve({ name: "customer-home" }).href;
        const menuPath = router.resolve({ name: "menu" }).href;
        const crumbs = [
          { name: t("seo.breadcrumbHome"), item: `${origin}${homePath}` },
          { name: t("seo.breadcrumbMenu"), item: `${origin}${menuPath}` },
        ];
        const categorySlug = String(route.params?.slug || route.params?.category || "").trim();
        if (categorySlug && (routeName === "category" || routeName === "dish")) {
          const cat = menu.categories.find((c) => c.slug === categorySlug);
          crumbs.push({
            name: String(cat?.name || categorySlug),
            item: `${origin}/browse/${categorySlug}`,
          });
        }
        if (routeName === "dish") {
          const dishSlug = String(route.params?.dish || "").trim();
          const dishList = menu.dishes[categorySlug] || [];
          const dishObj = dishList.find((d) => d.slug === dishSlug);
          if (dishSlug) {
            crumbs.push({
              name: String(dishObj?.name || dishSlug),
              item: `${origin}/browse/${categorySlug}/${dishSlug}`,
            });
          }
        }
        upsertJsonLd("tenant-breadcrumb-jsonld", {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: crumbs.map((crumb, idx) => ({
            "@type": "ListItem",
            position: idx + 1,
            name: crumb.name,
            item: crumb.item,
          })),
        });
      } else {
        upsertJsonLd("tenant-breadcrumb-jsonld", null);
      }

      // ── Per-item MenuItem/Product offer on the dish page ─────────────────────
      if (ITEM_ROUTE_NAMES.has(routeName)) {
        const categorySlug = String(route.params?.category || "").trim();
        const dishSlug = String(route.params?.dish || "").trim();
        const dishList = menu.dishes[categorySlug] || [];
        const dishObj = dishList.find((d) => d.slug === dishSlug) || null;
        if (dishObj && dishObj.name) {
          const rawPrice =
            dishObj.happy_hour && Number(dishObj.effective_price) < Number(dishObj.price)
              ? Number(dishObj.effective_price)
              : Number(dishObj.price);
          const dishImage = normalizeUrl(dishObj.image_url);
          const isProductVertical = ["grocery", "retail", "pharmacy"].includes(businessType);
          const itemType = isProductVertical ? "Product" : "MenuItem";
          const itemLd = {
            "@context": "https://schema.org",
            "@type": itemType,
            "@id": `${origin}/browse/${categorySlug}/${dishSlug}#item`,
            name: String(dishObj.name),
            ...(dishObj.description ? { description: String(dishObj.description) } : {}),
            ...(dishImage ? { image: dishImage } : {}),
            ...(Number.isFinite(rawPrice) && rawPrice >= 0
              ? {
                  offers: {
                    "@type": "Offer",
                    price: rawPrice,
                    priceCurrency: PRICE_CURRENCY,
                    availability:
                      dishObj.is_available === false
                        ? "https://schema.org/OutOfStock"
                        : "https://schema.org/InStock",
                    url: canonical,
                  },
                }
              : {}),
          };
          upsertJsonLd("tenant-menuitem-jsonld", itemLd);
        } else {
          upsertJsonLd("tenant-menuitem-jsonld", null);
        }
      } else {
        upsertJsonLd("tenant-menuitem-jsonld", null);
      }
    },
    { immediate: true }
  );
};
