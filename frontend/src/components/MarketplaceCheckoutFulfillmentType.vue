<template>
  <!-- Fulfillment type -->
  <div>
    <p class="text-xs font-medium text-slate-400 mb-1.5">{{ t('mktMenu.fulfillmentLabel') }}</p>
    <div class="flex gap-2">
      <button
        class="flex-1 rounded-xl border py-2.5 text-xs font-medium transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
        :class="fulfillmentType === 'pickup'
          ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
          : 'border-slate-700 text-slate-400 hover:border-slate-500'"
        :aria-pressed="fulfillmentType === 'pickup'"
        @click="fulfillmentType = 'pickup'"
      >{{ t('mktMenu.fulfillmentPickup') }}</button>
      <button
        v-if="deliveryEnabled"
        class="flex-1 rounded-xl border py-2.5 text-xs font-medium transition-colors ui-touch-target focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40"
        :class="fulfillmentType === 'delivery'
          ? 'border-sky-500/60 bg-sky-500/10 text-sky-300'
          : 'border-slate-700 text-slate-400 hover:border-slate-500'"
        :aria-pressed="fulfillmentType === 'delivery'"
        @click="fulfillmentType = 'delivery'"
      >{{ t('mktMenu.fulfillmentDelivery') }}</button>
    </div>
  </div>
</template>

<script setup>
// The pickup / delivery fulfillment-type selector of MarketplaceMenuPage.vue's
// checkout drawer, extracted as a small child (RISK FE-2) — sub-part 2 of the
// checkout-drawer split. The selected type is a two-way model bound to the parent's
// `form.fulfillment_type`, so switching it drives the same downstream logic
// (delivery form, fees, validation) the inline buttons did. The delivery button only
// shows when the restaurant supports delivery (`deliveryEnabled`). No logic here.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

/** The chosen fulfillment type (form.fulfillment_type), two-way. */
const fulfillmentType = defineModel('fulfillmentType', { type: String, default: 'pickup' });

defineProps({
  /** Whether the restaurant offers delivery (restaurant.delivery_enabled). */
  deliveryEnabled: { type: Boolean, default: false },
});
</script>
