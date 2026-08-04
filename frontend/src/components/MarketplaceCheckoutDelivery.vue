<template>
  <div class="space-y-2">
    <!-- Saved addresses — shown when customer is signed in and has saved addresses -->
    <div v-if="isAuthenticated && savedAddresses.length" class="space-y-1.5">
      <p class="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{{ t('mktMenu.savedAddresses') }}</p>
      <div class="space-y-1">
        <div
          v-for="addr in savedAddresses"
          :key="addr.id"
          class="flex min-w-0 w-full items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2 transition-colors hover:border-indigo-500/40 hover:bg-indigo-500/5"
        >
          <button
            type="button"
            class="min-w-0 flex-1 text-start text-xs focus-visible:outline-none"
            @click="emit('applyAddress', addr)"
          >
            <span v-if="addr.label" class="font-medium text-slate-200 me-0.5">{{ addr.label }} —</span>
            <span class="truncate text-slate-400">{{ addr.address }}</span>
          </button>
          <button
            type="button"
            class="shrink-0 text-slate-600 transition-colors hover:text-red-400 focus-visible:outline-none"
            :aria-label="t('mktMenu.deleteSavedAddress')"
            @click="emit('deleteAddress', addr.id)"
          >
            <svg viewBox="0 0 16 16" fill="currentColor" class="h-3 w-3" aria-hidden="true"><path d="M6 2h4a1 1 0 0 1 1 1v1H5V3a1 1 0 0 1 1-1ZM4 4H2v1h1l.8 8.1A1 1 0 0 0 4.8 14h6.4a1 1 0 0 0 1-.9L13 5h1V4H4Zm7 1H5l.7 7h4.6L12 5Z"/></svg>
          </button>
        </div>
      </div>
    </div>
    <div>
      <label for="mkt-address" class="block text-xs font-medium text-slate-400 mb-1">
        {{ t('mktMenu.deliveryAddress') }}
      </label>
      <textarea
        id="mkt-address"
        v-model="deliveryAddress"
        rows="2"
        :placeholder="t('mktMenu.deliveryAddressPlaceholder')"
        class="ui-textarea resize-none"
      />
    </div>
    <!-- Save address checkbox (authenticated customers only) -->
    <div v-if="isAuthenticated && deliveryAddress" class="space-y-1.5">
      <label class="flex items-center gap-2 cursor-pointer">
        <input v-model="saveAddress" type="checkbox" class="rounded" />
        <span class="text-xs text-slate-400">{{ t('mktMenu.saveAddress') }}</span>
      </label>
      <input
        v-if="saveAddress"
        v-model.trim="saveAddressLabel"
        type="text"
        class="ui-input text-xs"
        :placeholder="t('mktMenu.saveAddressLabelPlaceholder')"
        :aria-label="t('mktMenu.saveAddressLabelPlaceholder')"
      />
    </div>
    <!-- Coordinates → distance-based fee -->
    <button
      type="button"
      class="ui-press inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-slate-600 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
      :disabled="locating"
      :aria-busy="locating"
      @click="emit('locate')"
    >
      <svg v-if="locating" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
      <AppIcon v-else name="location" class="h-3 w-3 shrink-0" aria-hidden="true" />
      {{ locating ? t('mktMenu.locating') : (hasLocation ? t('mktMenu.locationSet') : t('mktMenu.useMyLocation')) }}
    </button>
    <p v-if="locateError" class="text-[11px] text-rose-300" role="alert">{{ locateError }}</p>
    <p v-if="outOfRange" class="flex items-start gap-1.5 text-[11px] text-rose-300" role="alert">
      <AppIcon name="info" class="h-3 w-3 shrink-0 mt-px" aria-hidden="true" />
      {{ t('mktMenu.deliveryOutOfRange', { km: radiusKm }) }}
    </p>
    <p v-else-if="feeIsDistance" class="flex items-center gap-1.5 text-[11px] text-slate-400">
      <AppIcon name="location" class="h-3 w-3 shrink-0" aria-hidden="true" />
      {{ t('mktMenu.deliveryFeeDistance', { fee: fmtPrice(deliveryFee), km: distanceKm }) }}
    </p>
    <p v-else-if="perKm > 0" class="flex items-center gap-1.5 text-[11px] text-amber-400" role="alert">
      <AppIcon name="location" class="h-3 w-3 shrink-0" aria-hidden="true" />
      {{ t('mktMenu.deliveryNeedsLocation') }}
    </p>
  </div>
</template>

<script setup>
// The delivery-details block of MarketplaceMenuPage.vue's checkout drawer (shown for
// delivery orders), extracted as a PRESENTATIONAL child (RISK FE-2) — the medium-risk
// part of the checkout-drawer split. It gathers the delivery address (saved-address
// picker + free-text + optional save-for-later) and the "use my location" affordance,
// and shows the resulting distance-fee / out-of-range / needs-location hints.
//
// It owns NO logic: the parent keeps geolocation (useMyLocation), the saved-address
// fetch/apply/delete (applyMktSavedAddress / deleteMktSavedAddress), and ALL the
// delivery-fee computeds — those results come in as props (locating / locateError /
// hasLocation / outOfRange / radiusKm / feeIsDistance / deliveryFee / distanceKm /
// perKm). The three editable fields (delivery_address / saveAddressAfterOrder /
// saveAddressLabel) are two-way models bound to the parent's refs; apply/delete/
// locate are emits. Markup + the v-model.trim on the label are verbatim.
import { useI18n } from '../composables/useI18n';
import AppIcon from './AppIcon.vue';

const { t } = useI18n();

/** The delivery address text (form.delivery_address), two-way. */
const deliveryAddress = defineModel('deliveryAddress', { type: String, default: '' });
/** Whether to save this address after ordering (saveAddressAfterOrder), two-way. */
const saveAddress = defineModel('saveAddress', { type: Boolean, default: false });
/** Optional label for the saved address (saveAddressLabel), two-way. */
const saveAddressLabel = defineModel('saveAddressLabel', { type: String, default: '' });

defineProps({
  /** Whether a customer is signed in (customerStore.isAuthenticated). */
  isAuthenticated: { type: Boolean, default: false },
  /** The customer's saved delivery addresses (mktSavedAddresses). */
  savedAddresses: { type: Array, default: () => [] },
  /** True while geolocation is resolving (locatingMkt). */
  locating: { type: Boolean, default: false },
  /** Geolocation error message, or '' (locateError). */
  locateError: { type: String, default: '' },
  /** Whether coordinates have been captured (form.delivery_lat) — drives the label. */
  hasLocation: { type: Boolean, default: false },
  /** Whether the address is outside the delivery radius (deliveryOutOfRange). */
  outOfRange: { type: Boolean, default: false },
  /** The delivery radius in km (deliveryPricing.radiusKm) for the out-of-range copy. */
  radiusKm: { type: [Number, String], default: 0 },
  /** Whether the fee is distance-based + resolved (deliveryFeeIsDistance). */
  feeIsDistance: { type: Boolean, default: false },
  /** The computed delivery fee (deliveryFee). */
  deliveryFee: { type: Number, default: 0 },
  /** The resolved distance in km (deliveryDistanceKm). */
  distanceKm: { type: [Number, String], default: 0 },
  /** Per-km delivery rate (deliveryPricing.perKm) — gates the needs-location hint. */
  perKm: { type: Number, default: 0 },
  /** Price formatter (fmtPrice). */
  fmtPrice: { type: Function, required: true },
});

const emit = defineEmits(['applyAddress', 'deleteAddress', 'locate']);
</script>
