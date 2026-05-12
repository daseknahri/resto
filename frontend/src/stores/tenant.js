import { defineStore } from "pinia";
import api from "../lib/api";
import { DEMO_TENANT_META } from "../lib/demoMenu";
import { translate } from "../i18n/translate";
import { hasPublicDemoTenant, isPublicDemoHost } from "../lib/runtimeHost";
import { useCartStore } from "./cart";

export const useTenantStore = defineStore("tenant", {
  state: () => ({ meta: null, loading: false, error: null }),
  getters: {
    resolvedMeta(state) {
      if (state.meta) return state.meta;
      if (isPublicDemoHost() && !hasPublicDemoTenant()) return DEMO_TENANT_META;
      return null;
    },
    entitlements() {
      const e = this.resolvedMeta?.entitlements;
      if (e && typeof e === "object") return e;
      const plan = this.resolvedMeta?.plan || {};
      const canCheckout = plan.can_checkout === true;
      // whatsapp + in_app_order default to true (open by default — gate later during tier work)
      const canWhatsapp = plan.can_whatsapp_order !== false;
      const canInAppOrder = plan.can_in_app_order !== false;
      return {
        tier_code: plan.tier_code || plan.code || "",
        tier_name: plan.tier_name || plan.name || "",
        ordering_mode: canCheckout ? "checkout" : canWhatsapp ? "whatsapp" : canInAppOrder ? "in_app" : "menu_only",
        can_order: canCheckout || canWhatsapp || canInAppOrder,
        can_checkout: canCheckout,
        can_whatsapp_order: canWhatsapp,
        can_in_app_order: canInAppOrder,
        max_languages: plan.max_languages || 1,
        is_active: plan.is_active !== false,
      };
    },
    isBrowseOnlyPlan() {
      const mode = this.entitlements?.ordering_mode;
      if (mode) return mode === "menu_only";
      return false;
    },
    /**
     * Check if a plan feature flag is enabled.
     * TODO: restore per-flag gating once tier work is complete.
     * For now always returns true so all owner features are accessible for testing.
     */
    hasFlag() {
      return (_key) => true;
    },
  },
  actions: {
    mergeProfile(profile) {
      if (!this.meta || !profile || typeof profile !== "object") return;
      this.meta = {
        ...this.meta,
        profile: {
          ...(this.meta.profile || {}),
          ...profile,
        },
      };
    },
    syncCartEntitlements() {
      const cart = useCartStore();
      const canCheckout = this.entitlements?.can_checkout === true;
      const canWhatsapp = this.entitlements?.can_whatsapp_order === true;
      const canInAppOrder = this.entitlements?.can_in_app_order !== false;
      cart.setCanCheckout(canCheckout);
      cart.setCanWhatsapp(canWhatsapp);
      if (!canCheckout && !canWhatsapp && !canInAppOrder && cart.items.length) {
        cart.clear();
      }
    },
    async fetchMeta() {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/meta/", { params: { force_locale: 1 } });
        this.meta = res.data;
        this.syncCartEntitlements();
      } catch (err) {
        this.error = isPublicDemoHost() && !hasPublicDemoTenant() ? null : translate("tenantStore.loadFailed");
        this.syncCartEntitlements();
        if (!(isPublicDemoHost() && !hasPublicDemoTenant())) console.error(err);
      } finally {
        this.loading = false;
      }
    },
  },
});
