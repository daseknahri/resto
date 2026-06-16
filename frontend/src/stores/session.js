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
    // Must match the backend admin endpoints, which require the PLATFORM_SUPERADMIN
    // role (is_platform_admin) — not merely Django is_staff/is_superuser. Using the
    // looser can_access_admin_console here let staff/superusers load admin pages that
    // then 403 on every data call.
    isPlatformAdmin: (state) => state.user?.is_platform_admin === true,
    canEditTenantMenu: (state) => state.user?.can_edit_tenant_menu === true,
    isTenantStaff: (state) => state.user?.role === "tenant_staff",
    isTenantOwner: (state) => state.user?.role === "tenant_owner",
    // Granular permissions — owners always have all; staff respect their flags.
    // Falls back to true for owners (so no code changes needed in owner-only pages).
    canManageOrders: (state) => state.user?.permissions?.manage_orders !== false,
    canViewRevenue: (state) => state.user?.permissions?.view_revenue !== false,
    canEditMenu: (state) => state.user?.permissions?.edit_menu !== false,
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
        let resolvedUser = authenticated ? userPayload : null;

        // Auto-repair: if the user is a tenant_owner but their tenant FK was
        // NULLed (e.g. tenant was deleted + recreated with a new PK), all
        // owner API calls will 403.  Call the repair endpoint once so the link
        // is restored, then re-read the refreshed session payload.
        if (resolvedUser?.role === "tenant_owner" && resolvedUser?.tenant === null) {
          try {
            const repair = await api.post("/repair-tenant-link/");
            if (repair.data?.user) {
              resolvedUser = repair.data.user;
            }
          } catch {
            // Best-effort; proceed with the original (broken) user so the UI
            // can at least show a meaningful error rather than a blank page.
          }
        }

        this.user = resolvedUser;
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
        const { data, status } = await api.post("/login/", { identifier, password });
        // HTTP 202 means MFA is required — do NOT set the user yet.
        if (status === 202 || data?.mfa_required === true) {
          this.user = null;
          this.loaded = false;
          return { mfaRequired: true };
        }
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
    async verifyMfa({ code, backup_code }) {
      this.loading = true;
      this.error = null;
      try {
        const payload = backup_code ? { backup_code } : { code };
        const { data } = await api.post("/mfa/verify/", payload);
        this.user = data?.user || null;
        this.loaded = true;
        return this.user;
      } catch (err) {
        this.user = null;
        this.loaded = false;
        this.error = extractErrorMessage(err, translate("sessionStore.mfaInvalidCode"));
        throw err;
      } finally {
        this.loading = false;
      }
    },
    async signOut() {
      try {
        await api.post("/logout/");
      } catch {
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
