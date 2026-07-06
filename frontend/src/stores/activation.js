import api from "../lib/api";
import { defineStore } from "pinia";

// The backend's ActivationSerializer.validate raises plain (non-field) DRF
// ValidationErrors, which the exception handler surfaces as
// {"non_field_errors": ["<message>"]} rather than {"detail": ...}. Match on
// the exact server-side string (always English, independent of UI locale) so
// the "expired or used" case can be detected without fragile substring
// matching on translated text.
const TOKEN_EXPIRED_OR_USED = "Token expired or used";

const extractErrorMessage = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.non_field_errors) && data.non_field_errors.length) {
    return String(data.non_field_errors[0]);
  }
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};

export const useActivationStore = defineStore("activation", {
  state: () => ({ submitting: false, error: null, success: false, tokenExpiredOrUsed: false }),
  actions: {
    async activate(token, password) {
      this.submitting = true;
      this.error = null;
      this.success = false;
      this.tokenExpiredOrUsed = false;
      try {
        await api.post("/activate/", { token, password });
        this.success = true;
      } catch (err) {
        this.error = extractErrorMessage(err, "Activation failed");
        this.tokenExpiredOrUsed = this.error === TOKEN_EXPIRED_OR_USED;
      } finally {
        this.submitting = false;
      }
    },
  },
});
