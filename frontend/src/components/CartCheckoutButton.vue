<template>
  <button
    class="ui-btn-outline w-full justify-center py-2.5 text-sm font-semibold"
    :disabled="busy"
    :aria-busy="busy"
    @click="emit('checkout')"
  >
    <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
    <AppIcon v-else name="card" class="h-4 w-4" />
    {{ label }}
  </button>
</template>

<script setup>
// The "proceed to checkout" (PSP) CTA button of Cart.vue, extracted as a DUMB
// presentational button (RISK FE-2). It owns NO checkout logic: the parent
// (Cart.vue) keeps `startCheckout` and the `processingCheckout` state — those are
// passed in verbatim as `busy` / `label`, and the tap forwards intent via the
// `checkout` emit. This component only renders the button chrome (busy spinner vs
// card icon, and the label). It never initiates or validates a checkout.
import AppIcon from './AppIcon.vue';

defineProps({
  /** Whether the checkout request is in flight (processingCheckout). */
  busy: { type: Boolean, default: false },
  /** The button label (the parent's processingCheckout-aware label, verbatim). */
  label: { type: String, default: '' },
});

const emit = defineEmits(['checkout']);
</script>
