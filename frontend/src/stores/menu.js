import { defineStore } from "pinia";
import api from "../lib/api";
import { buildDemoDishesByCategory, DEMO_CATEGORIES } from "../lib/demoMenu";
import { translate } from "../i18n/translate";
import { isPublicDemoHost } from "../lib/runtimeHost";

const normalizeDishes = (value) => {
  if (!Array.isArray(value)) return [];
  return value.map((item) => ({
    ...item,
    options: Array.isArray(item?.options) ? item.options : [],
  }));
};

const normalizeCategories = (value) => {
  const rows = Array.isArray(value) ? value : Array.isArray(value?.results) ? value.results : [];
  return rows.map((item) => ({
    ...item,
    dishes: normalizeDishes(item?.dishes),
  }));
};

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
    categories: [],
    dishes: {},
    loading: false,
    error: null,
  }),
  actions: {
    applyDemoMenuData() {
      this.categories = demoCategories();
      this.dishes = demoDishesByCategory();
      this.error = null;
    },
    async fetchCategories() {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/categories/");
        const normalized = normalizeCategories(res.data);
        if (normalized.length || !isPublicDemoHost()) {
          this.categories = normalized;
          if (!Object.keys(this.dishes).length) {
            this.dishes = Object.fromEntries(normalized.map((category) => [category.slug, category.dishes || []]));
          }
        } else {
          this.applyDemoMenuData();
        }
      } catch (err) {
        if (isPublicDemoHost()) {
          this.applyDemoMenuData();
        } else {
          this.categories = [];
          this.error = extractErrorMessage(err, translate("menuStore.loadCategoriesFailed"));
          if (!isExpectedPublicStateError(err)) console.error(err);
        }
      } finally {
        this.loading = false;
      }
    },
    async fetchDishesByCategory(slug) {
      if (this.dishes[slug]?.length) return;
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/dishes/", { params: { category: slug } });
        this.dishes[slug] = normalizeDishes(res.data);
      } catch (err) {
        if (isPublicDemoHost()) {
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
