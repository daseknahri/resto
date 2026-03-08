import { defineStore } from "pinia";
import api from "../lib/api";

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
    async fetchCategories() {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/categories/");
        this.categories = res.data;
      } catch (err) {
        this.categories = [];
        this.error = extractErrorMessage(err, "Unable to load categories");
        if (!isExpectedPublicStateError(err)) console.error(err);
      } finally {
        this.loading = false;
      }
    },
    async fetchDishesByCategory(slug) {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/dishes/", { params: { category: slug } });
        this.dishes[slug] = res.data;
      } catch (err) {
        this.dishes[slug] = [];
        this.error = extractErrorMessage(err, "Unable to load dishes");
        if (!isExpectedPublicStateError(err)) console.error(err);
      } finally {
        this.loading = false;
      }
    },
  },
});
