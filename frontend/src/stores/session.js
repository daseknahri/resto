import { defineStore } from "pinia";
import api from "../lib/api";
import { translate } from "../i18n/translate";

const extractErrorMessage = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.non_field_errors) && data.non_field_errors.length) {
    return String(data.non_field_errors[0]);
  }
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};

export const useSessionStore = defineStore("session", {
  state: () => ({
    user: null,
    loading: false,
    loaded: false,
    error: null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.user,
    isPlatformAdmin: (state) => state.user?.can_access_admin_console === true,
    canEditTenantMenu: (state) => state.user?.can_edit_tenant_menu === true,
  },
  actions: {
    async fetchSession(force = false) {
      if (this.loaded && this.user && !force) return this.user;
      this.loading = true;
      this.error = null;
      try {
        const { data } = await api.get("/session/");
        const authenticated = data?.authenticated === true || (data?.user && data.user.id);
        const userPayload = data?.user ?? data;
        this.user = authenticated ? userPayload : null;
        this.loaded = true;
        return this.user;
      } catch (err) {
        this.user = null;
        this.loaded = false;
        this.error = extractErrorMessage(err, translate("sessionStore.notAuthenticated"));
        throw err;
      } finally {
        this.loading = false;
      }
    },
    async signIn(identifier, password) {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await api.post("/login/", { identifier, password });
        this.user = data?.user || null;
        this.loaded = true;
        return this.user;
      } catch (err) {
        this.user = null;
        this.loaded = false;
        this.error = extractErrorMessage(err, translate("sessionStore.signInFailed"));
        throw err;
      } finally {
        this.loading = false;
      }
    },
    async signOut() {
      try {
        await api.post("/logout/");
      } catch (err) {
        // keep local clear even if API fails
      } finally {
        this.clear();
      }
    },
    clear() {
      this.user = null;
      this.loading = false;
      this.loaded = false;
      this.error = null;
    },
  },
});
