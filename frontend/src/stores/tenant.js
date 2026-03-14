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
      const canWhatsapp = plan.can_whatsapp_order === true;
      return {
        tier_code: plan.tier_code || plan.code || "",
        tier_name: plan.tier_name || plan.name || "",
        ordering_mode: canCheckout ? "checkout" : canWhatsapp ? "whatsapp" : "menu_only",
        can_order: canCheckout || canWhatsapp,
        can_checkout: canCheckout,
        can_whatsapp_order: canWhatsapp,
        max_languages: plan.max_languages || 1,
        is_active: plan.is_active !== false,
      };
    },
    isBrowseOnlyPlan() {
      const mode = this.entitlements?.ordering_mode;
      if (mode) return mode === "menu_only";
      return false;
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
      cart.setCanCheckout(canCheckout);
      cart.setCanWhatsapp(canWhatsapp);
      if (!canCheckout && !canWhatsapp && cart.items.length) {
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
