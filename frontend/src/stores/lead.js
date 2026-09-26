import { defineStore } from "pinia";
import api, { extractApiErrorMessage } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { translate } from "../i18n/translate";
import { useToastStore } from "./toast";

const extractErrorMessage = extractApiErrorMessage;  // shared canonical extractor (lib/api)

export const useLeadStore = defineStore("lead", {
  state: () => ({
    submitting: false,
    error: null,
    success: false,
    fullyBooked: false,
    fullyBookedData: null, // { booked_for, used, max }
  }),
  actions: {
    async submitLead(payload) {
      const toast = useToastStore();
      this.submitting = true;
      this.error = null;
      this.success = false;
      this.fullyBooked = false;
      this.fullyBookedData = null;
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
        // Handle capacity-full (409) without showing a generic toast
        if (err?.response?.status === 409 && err?.response?.data?.detail === "fully_booked") {
          this.fullyBooked = true;
          this.fullyBookedData = err.response.data || null;
          return;
        }
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
      this.fullyBooked = false;
      this.fullyBookedData = null;
    },
  },
});
