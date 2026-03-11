import { defineStore } from "pinia";
import api from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { translate } from "../i18n/translate";
import { useToastStore } from "./toast";

const extractErrorMessage = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.non_field_errors) && data.non_field_errors.length) return String(data.non_field_errors[0]);
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};

export const useLeadStore = defineStore("lead", {
  state: () => ({
    submitting: false,
    error: null,
    success: false,
  }),
  actions: {
    async submitLead(payload) {
      const toast = useToastStore();
      this.submitting = true;
      this.error = null;
      this.success = false;
      try {
        await api.post("/leads/", payload);
        this.success = true;
        const source = String(payload?.source || "lead_form");
        trackEvent(
          "lead_submit",
          { source, metadata: { plan_code: payload?.plan_code || "", has_phone: Boolean(payload?.phone) } },
          { once: false }
        );
        toast.show(translate("leadStore.received"), "success");
      } catch (err) {
        this.error = extractErrorMessage(err, translate("leadStore.submitFailed"));
        toast.show(this.error, "error");
      } finally {
        this.submitting = false;
      }
    },
    reset() {
      this.submitting = false;
      this.error = null;
      this.success = false;
    },
  },
});
