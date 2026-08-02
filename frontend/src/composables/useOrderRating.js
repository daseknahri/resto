import { ref } from "vue";
import api from "../lib/api";
import { useToastStore } from "../stores/toast";
import { useI18n } from "./useI18n";

// Map a backend rating-rejection code to its i18n key SUFFIX (the surface supplies the
// namespace prefix). These were copy-pasted in OrderStatus.vue and MarketplaceOrderStatus.vue
// ("mirrors OrderStatus.vue's mapping"); the reachable outcomes from CustomerOrderRateView (B5)
// are already_rated / order_not_completed / not_order_owner / invalid_score.
export function ratingErrorKey(err) {
  const code = err?.response?.data?.code;
  if (code === "already_rated") return "rateErrorAlreadyRated";
  if (code === "order_not_completed") return "rateErrorNotCompleted";
  if (code === "not_order_owner") return "rateErrorNotOwner";
  if (code === "invalid_score") return "rateErrorInvalidScore";
  return "rateError";
}

/**
 * Shared 1–5 star order rating for the two order-status pages (tenant + marketplace).
 * Both POST /orders/<n>/rate/ with the same payload and the same error-code mapping; only the
 * i18n namespace and the post-success behavior differ, so those are injected.
 *
 * @param {object}   opts
 * @param {() => string} opts.getOrderNumber  resolves the order number at submit time
 * @param {string}   opts.i18nPrefix          e.g. "orderStatus" | "mktOrderStatus"
 * @param {() => (void|Promise<void>)} [opts.onRated]  per-page success behavior (toast / refetch / flag)
 * @returns {{ score, comment, submitting, submit }} refs + the submit action
 */
export function useOrderRating({ getOrderNumber, i18nPrefix, onRated }) {
  const { t } = useI18n();
  const toast = useToastStore();
  const score = ref(0);
  const comment = ref("");
  const submitting = ref(false);

  const submit = async () => {
    if (score.value === 0 || submitting.value) return;
    submitting.value = true;
    try {
      await api.post(`/orders/${getOrderNumber()}/rate/`, {
        score: score.value,
        comment: comment.value.trim(),
      });
      if (onRated) await onRated();
    } catch (err) {
      toast.show(t(`${i18nPrefix}.${ratingErrorKey(err)}`), "error");
    } finally {
      submitting.value = false;
    }
  };

  return { score, comment, submitting, submit };
}
