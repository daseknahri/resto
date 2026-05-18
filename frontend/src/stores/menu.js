import { defineStore } from "pinia";
import api from "../lib/api";
import { buildDemoDishesByCategory, DEMO_CATEGORIES } from "../lib/demoMenu";
import { translate } from "../i18n/translate";
import { hasPublicDemoTenant, isPublicDemoHost } from "../lib/runtimeHost";
import { readCache, isFresh, writeCache } from "../lib/staleCache";

// Shorter TTL than tenant meta — dish availability (is_available) changes
// during service when the owner 86s an item. 2 min means at most a 2-minute
// window where a sold-out dish still appears available to new visitors.
const MENU_CACHE = "menu.categories";
const MENU_TTL   = 2 * 60 * 1000; // 2 minutes

const normalizeDishes = (value) => {
  if (!Array.isArray(value)) return [];
  return value.map((item) => ({
    ...item,
    options: Array.isArray(item?.options) ? item.options : [],
    option_groups: Array.isArray(item?.option_groups) ? item.option_groups : [],
    tags: Array.isArray(item?.tags) ? item.tags : [],
    allergens: Array.isArray(item?.allergens) ? item.allergens : [],
  }));
};

const normalizeCategories = (value) => {
  const rows = Array.isArray(value) ? value : Array.isArray(value?.results) ? value.results : [];
  return rows.map((item) => ({
    ...item,
    dishes: normalizeDishes(item?.dishes),
  }));
};

const normalizeSuperCategories = (value) => {
  const rows = Array.isArray(value) ? value : Array.isArray(value?.results) ? value.results : [];
  return rows.map((item) => ({
    ...item,
  }));
};

const demoSuperCategories = () => [
  {
    id: 1,
    slug: "menu",
    name: "Menu",
    position: 0,
    is_published: true,
    is_temporarily_disabled: false,
    disabled_note: "",
    category_count: DEMO_CATEGORIES.length,
  },
];

const demoCategories = () => normalizeCategories(DEMO_CATEGORIES);
const demoDishesByCategory = () => buildDemoDishesByCategory();

const extractErrorMessage = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") {
    if (typeof data?.note === "string" && data.note.trim()) {
      return `${data.detail} ${data.note}`;
    }
    return data.detail;
  }
  if (Array.isArray(data?.non_field_errors) && data.non_field_errors.length) return String(data.non_field_errors[0]);
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};

const isExpectedPublicStateError = (err) => {
  const status = err?.response?.status;
  const code = err?.response?.data?.code;
  if (status === 403) return true;
  if (status === 503 && code === "menu_temporarily_disabled") return true;
  return false;
};

export const useMenuStore = defineStore("menu", {
  state: () => ({
    superCategories: [],
    categories: [],
    dishes: {},
    loading: false,
    error: null,
  }),
  actions: {
    applyDemoMenuData() {
      this.superCategories = demoSuperCategories();
      this.categories = demoCategories();
      this.categories = this.categories.map((category) => ({
        ...category,
        super_category: 1,
        super_category_slug: "menu",
        super_category_name: "Menu",
      }));
      this.dishes = demoDishesByCategory();
      this.error = null;
    },
    async fetchSuperCategories(force = false) {
      if (!force && this.superCategories.length) return;
      try {
        const res = await api.get("/super-categories/", { params: { force_locale: 1 } });
        const normalized = normalizeSuperCategories(res.data);
        if (normalized.length || !isPublicDemoHost() || hasPublicDemoTenant()) {
          this.superCategories = normalized;
        } else {
          this.superCategories = demoSuperCategories();
        }
      } catch (err) {
        if (isPublicDemoHost() && !hasPublicDemoTenant()) {
          this.superCategories = demoSuperCategories();
        } else {
          this.superCategories = [];
          if (!isExpectedPublicStateError(err)) console.error(err);
        }
      }
    },
    async fetchCategories(force = false) {
      const isDemo = isPublicDemoHost() && !hasPublicDemoTenant();

      // ── 1. Serve stale cache instantly ──────────────────────────────────────
      // Repeat visitors (and page navigations) see the full menu immediately.
      // We only skip the cache when `force=true` (e.g. after the owner saves).
      if (!force && !isDemo) {
        const cached = readCache(MENU_CACHE);
        if (cached) {
          this.superCategories = cached.superCategories ?? [];
          this.categories      = cached.categories      ?? [];
          this.dishes          = cached.dishes          ?? {};
          this.error           = null;
          this.loading         = false;
          // Still fresh → nothing more to do this visit
          if (isFresh(MENU_CACHE, MENU_TTL)) return;
          // Stale → background revalidate below (no spinner — UI is already populated)
        }
      }

      // ── 2. Fetch fresh data ─────────────────────────────────────────────────
      // Show spinner only when we have nothing at all to display yet.
      if (!this.categories.length) this.loading = true;
      this.error = null;

      try {
        // fetchSuperCategories skips its own API call if superCategories is
        // already populated (from cache or a prior call this session).
        await this.fetchSuperCategories(force);
        const res = await api.get("/categories/", { params: { force_locale: 1 } });
        const normalized = normalizeCategories(res.data);

        if (normalized.length || !isPublicDemoHost() || hasPublicDemoTenant()) {
          this.categories = normalized;
          // Always refresh dishes from a successful fetch so that is_available
          // status changes propagate to existing cache entries promptly.
          this.dishes = Object.fromEntries(
            normalized.map((category) => [category.slug, category.dishes || []])
          );
          // Persist fresh snapshot for next visit
          if (!isDemo) {
            writeCache(MENU_CACHE, {
              superCategories: this.superCategories,
              categories:      this.categories,
              dishes:          this.dishes,
            });
          }
        } else {
          this.applyDemoMenuData();
        }
      } catch (err) {
        if (isPublicDemoHost() && !hasPublicDemoTenant()) {
          this.applyDemoMenuData();
        } else if (!this.categories.length) {
          // Only surface an error when there is nothing to show the user.
          // If we already painted stale data, a background failure is silent.
          this.superCategories = [];
          this.categories = [];
          this.error = extractErrorMessage(err, translate("menuStore.loadCategoriesFailed"));
          if (!isExpectedPublicStateError(err)) console.error(err);
        }
      } finally {
        this.loading = false;
      }
    },
    async fetchDishesByCategory(slug, force = false) {
      if (!force && this.dishes[slug]?.length) return;
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/dishes/", { params: { category: slug, force_locale: 1 } });
        this.dishes[slug] = normalizeDishes(res.data);
      } catch (err) {
        if (isPublicDemoHost() && !hasPublicDemoTenant()) {
          this.dishes[slug] = demoDishesByCategory()[slug] || [];
        } else {
          this.dishes[slug] = [];
          this.error = extractErrorMessage(err, translate("menuStore.loadDishesFailed"));
          if (!isExpectedPublicStateError(err)) console.error(err);
        }
      } finally {
        this.loading = false;
      }
    },
  },
});
