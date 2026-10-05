import api, { extractApiErrorMessage } from "../lib/api";
import { defineStore } from "pinia";

// The backend's ActivationSerializer.validate raises plain (non-field) DRF
// ValidationErrors, which the exception handler surfaces as
// {"non_field_errors": ["<message>"]} rather than {"detail": ...}. Match on
// the exact server-side string (always English, independent of UI locale) so
// the "expired or used" case can be detected without fragile substring
// matching on translated text.
const TOKEN_EXPIRED_OR_USED = "Token expired or used";
// accounts.serializers.ACTIVATION_ALREADY_DONE — the account has signed in or
// enrolled MFA, so the page offers Sign in / Forgot password instead.
const ALREADY_ACTIVATED_PREFIX = "This account is already activated";

const extractErrorMessage = extractApiErrorMessage;  // shared canonical extractor (lib/api)

export const useActivationStore = defineStore("activation", {
  state: () => ({ submitting: false, error: null, success: false, tokenExpiredOrUsed: false, alreadyActivated: false }),
  actions: {
    async activate(token, password) {
      this.submitting = true;
      this.error = null;
      this.success = false;
      this.tokenExpiredOrUsed = false;
      this.alreadyActivated = false;
      try {
        await api.post("/activate/", { token, password });
        this.success = true;
      } catch (err) {
        this.error = extractErrorMessage(err, "Activation failed");
        this.tokenExpiredOrUsed = this.error === TOKEN_EXPIRED_OR_USED;
        this.alreadyActivated = typeof this.error === "string" && this.error.startsWith(ALREADY_ACTIVATED_PREFIX);
      } finally {
        this.submitting = false;
      }
    },
  },
});
