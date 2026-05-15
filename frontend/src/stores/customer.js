import { defineStore } from "pinia";
import api from "../lib/api";

export const useCustomerStore = defineStore("customer", {
  state: () => ({
    /** @type {{ id: number, name: string, email: string, phone: string, phone_verified: boolean, email_verified: boolean, has_google: boolean } | null} */
    customer: null,
    loaded: false,
    loading: false,
  }),

  getters: {
    isAuthenticated: (state) => state.customer !== null,
    displayName: (state) => state.customer?.name || state.customer?.phone || state.customer?.email || "",
  },

  actions: {
    async fetchCustomer(force = false) {
      if (this.loaded && !force) return;
      this.loading = true;
      try {
        const { data } = await api.get("/customer/session/");
        this.customer = data.customer || null;
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
