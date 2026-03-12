import api from "../lib/api";
import { defineStore } from "pinia";

export const useActivationStore = defineStore("activation", {
  state: () => ({ submitting: false, error: null, success: false }),
  actions: {
    async activate(token, password) {
      this.submitting = true;
      this.error = null;
      this.success = false;
      try {
        await api.post("/activate/", { token, password });
        this.success = true;
      } catch (err) {
        this.error = err.response?.data?.detail || "Activation failed";
      } finally {
        this.submitting = false;
      }
    },
  },
});
