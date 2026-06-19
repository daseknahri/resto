import { defineStore } from "pinia";
import api from "../lib/api";

export const useCustomerStore = defineStore("customer", {
  state: () => ({
    /** @type {{ id: number, name: string, email: string, phone: string, phone_verified: boolean, email_verified: boolean, has_google: boolean, wallet_balance: string } | null} */
    customer: null,
    /** @type {{ psp_topup_enabled: boolean } | null} */
    platform: null,
    loaded: false,
    loading: false,
  }),

  getters: {
    isAuthenticated: (state) => state.customer !== null,
    displayName: (state) => state.customer?.name || state.customer?.phone || state.customer?.email || "",
    /** True when the customer has at least one verified contact method (phone OTP, email OTP, or Google). */
    isVerified: (state) =>
      !!(state.customer?.phone_verified || state.customer?.email_verified || state.customer?.has_google),
    /** Preferred locale for the customer (en/fr/ar). */
    locale: (state) => state.customer?.locale || "en",
    /** Platform-enabled verticals (food/shops/pharmacy/rides/courier/driver). P4. */
    enabledVerticals: (state) => state.platform?.enabled_verticals || [],
    /** Whether a given vertical is enabled platform-wide. P4. */
    isVerticalEnabled: (state) => (vertical) =>
      (state.platform?.enabled_verticals || []).includes(vertical),
  },

  actions: {
    async fetchCustomer(force = false) {
      // Guard 1: already resolved for this page session
      if (this.loaded && !force) return;
      // Guard 2: a fetch is already in flight — don't fire a second request
      if (this.loading) return;
      this.loading = true;
      try {
        const { data } = await api.get("/customer/session/");
        this.customer = data.customer || null;
        this.platform = data.platform || null;
      } catch {
        this.customer = null;
      } finally {
        this.loaded = true;
        this.loading = false;
      }
    },

    setCustomer(customer) {
      this.customer = customer || null;
      this.loaded = true;
      this.loading = false;
    },

    async logout() {
      try {
        await api.delete("/customer/session/");
      } catch {
        // ignore
      }
      this.customer = null;
    },
  },
});
