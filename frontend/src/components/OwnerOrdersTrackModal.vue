<template>
  <!-- Live delivery tracking modal (owner follows the driver on a map) -->
  <div
    v-if="open"
    class="fixed inset-0 z-[2100] flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
    @click.self="emit('close')"
    @keydown.esc="emit('close')"
  >
    <div class="ui-panel w-full max-w-lg overflow-hidden rounded-t-2xl sm:rounded-2xl" role="dialog" aria-modal="true" aria-labelledby="track-modal-heading">
      <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <h3 id="track-modal-heading" class="text-sm font-semibold text-slate-100">
          {{ t("ownerOrders.trackTitle") }} <span class="text-slate-500">#{{ orderNumber }}</span>
        </h3>
        <button class="ui-btn-outline ui-press px-3 py-1.5 text-xs" @click="emit('close')">{{ t("common.close") }}</button>
      </div>
      <div class="p-4">
        <p v-if="error" class="ui-empty-state py-6 text-center text-sm text-slate-400">
          {{ error }}
        </p>
        <DeliveryTracker v-else-if="delivery" :delivery="delivery" />
        <div v-else class="ui-skeleton h-48" aria-busy="true" :aria-label="t('common.loading')" />
      </div>
    </div>
  </div>
</template>

<script setup>
// Live delivery-tracking modal of OwnerOrders.vue, extracted as a standalone
// presentational child (RISK FE-2). This is DISPLAY ONLY: it renders whatever
// tracking state the parent hands it (order number, the polled `delivery`
// payload → DeliveryTracker, an error, or a loading skeleton) and asks the parent
// to close via the `close` emit.
//
// IMPORTANT — the entanglement stays in the parent: OwnerOrders.vue owns the
// `trackModal` ref, the 10s poll (`_trackPoll` / `fetchTrack`), openTrack and
// closeTrack (which stops the interval). Because `trackModal` is a deep-reactive
// ref, the parent binding `:delivery="trackModal.delivery"` stays reactive as the
// poll mutates it, so DeliveryTracker re-renders on each tick exactly as before.
import DeliveryTracker from './DeliveryTracker.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Whether the modal is open (parent-owned trackModal.open). */
  open: { type: Boolean, default: false },
  /** The tracked order's number, for the heading. */
  orderNumber: { type: [String, Number], default: '' },
  /** The latest polled delivery payload, or null while loading. */
  delivery: { type: Object, default: null },
  /** A load/track error message, or empty. */
  error: { type: String, default: '' },
});

const emit = defineEmits(['close']);
</script>
