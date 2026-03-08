import { defineStore } from "pinia";
import api from "../lib/api";
import { useCartStore } from "./cart";

export const useTenantStore = defineStore("tenant", {
  state: () => ({ meta: null, loading: false, error: null }),
  getters: {
    entitlements(state) {
      const e = state.meta?.entitlements;
      if (e && typeof e === "object") return e;
      const plan = state.meta?.plan || {};
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
    isBrowseOnlyPlan(state) {
      const mode = this.entitlements?.ordering_mode;
      if (mode) return mode === "menu_only";
      return false;
    },
  },
  actions: {
    async fetchMeta() {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/meta/");
        this.meta = res.data;
        const cart = useCartStore();
        const canCheckout = this.entitlements?.can_checkout === true;
        const canWhatsapp = this.entitlements?.can_whatsapp_order === true;
        cart.setCanCheckout(canCheckout);
        cart.setCanWhatsapp(canWhatsapp);
        if (!canCheckout && !canWhatsapp && cart.items.length) {
          cart.clear();
        }
      } catch (err) {
        this.error = "Unable to load tenant settings";
        console.error(err);
      } finally {
        this.loading = false;
      }
    },
  },
});
