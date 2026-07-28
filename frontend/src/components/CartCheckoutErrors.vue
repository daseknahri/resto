<template>
  <!-- Errors -->
  <div
    v-for="(msg, i) in messages"
    :key="i"
    class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
    role="alert"
  >
    <AppIcon name="info" aria-hidden="true" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" />
    <p class="flex-1 text-sm text-red-300">{{ msg }}</p>
  </div>
</template>

<script setup>
// Checkout error alerts of Cart.vue, extracted as a standalone presentational
// child (RISK FE-2). DISPLAY ONLY: it renders one red alert per non-empty error
// message (place-order / checkout / handoff), in that order. It owns no state and
// triggers nothing — the parent (Cart.vue) keeps the place-order / payment / PSP-
// checkout flows and just passes in whatever error strings they set. No money,
// payment or order-placement logic lives here.
import { computed } from 'vue';
import AppIcon from './AppIcon.vue';

const props = defineProps({
  /** Error from the in-app place-order flow (placeInAppOrder), or ''. */
  placeOrderError: { type: String, default: '' },
  /** Error from the PSP checkout flow (startCheckout), or ''. */
  checkoutError: { type: String, default: '' },
  /** Error from the order handoff, or ''. */
  handoffError: { type: String, default: '' },
});

// Same three alerts as the original, in the same order — collapsed to a v-for over
// the non-empty ones (each was an identical role="alert" block).
const messages = computed(() =>
  [props.placeOrderError, props.checkoutError, props.handoffError].filter(Boolean),
);
</script>
