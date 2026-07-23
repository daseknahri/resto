<template>
  <button
    class="ui-btn-primary w-full justify-center py-4 text-base font-bold tracking-wide shadow-lg shadow-[var(--color-secondary)]/20"
    :disabled="disabled"
    :aria-busy="busy"
    @click="emit('place')"
  >
    <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
    <AppIcon v-else name="cart" class="h-4 w-4 shrink-0" aria-hidden="true" />
    {{ label }}
  </button>
</template>

<script setup>
// The primary "place order" CTA button of Cart.vue, extracted as a DUMB
// presentational button (RISK FE-2). It owns NO checkout logic whatsoever: the
// parent (Cart.vue) keeps `placeInAppOrder`, the full disabled condition, and the
// label computation — those are passed in verbatim as `disabled` / `busy` / `label`,
// and the tap forwards intent via the `place` emit (the parent runs placeInAppOrder).
// This component only renders the button chrome (the busy spinner vs the cart icon
// and the label). It never charges, places, or validates an order.
import AppIcon from './AppIcon.vue';

defineProps({
  /** Whether the place-order request is in flight (placingOrder) — spinner + aria-busy. */
  busy: { type: Boolean, default: false },
  /** Whether the button is disabled (the parent's full block condition, verbatim). */
  disabled: { type: Boolean, default: false },
  /** The button label (the parent's status-aware label expression, verbatim). */
  label: { type: String, default: '' },
});

const emit = defineEmits(['place']);
</script>
