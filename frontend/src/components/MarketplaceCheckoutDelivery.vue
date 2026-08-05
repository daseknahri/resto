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
        :aria-invalid="addressError ? 'true' : undefined"
        aria-describedby="mkt-address-error"
      />
      <p v-if="addressError" id="mkt-address-error" role="alert" class="mt-1 text-xs text-red-300">{{ addressError }}</p>
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

    <!-- No-GPS fallback (parity with the tenant Cart): when the fee is priced per-km, a
         customer who denies geolocation / is on desktop / times out can still set a
         delivery point by pasting a map link or typing coordinates. Without this the
         order dead-ends — Place Order stays permanently disabled (needsLocation). The
         section auto-reveals when a locate attempt just failed. -->
    <div v-if="perKm > 0" class="space-y-2 pt-1">
      <button
        type="button"
        class="ui-press inline-flex items-center gap-1 rounded text-[11px] font-medium text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
        :aria-expanded="manualOpen"
        @click="showManual = !showManual"
      >
        <span aria-hidden="true" class="text-[10px]">{{ manualOpen ? '▾' : '▸' }}</span>
        {{ t('mktMenu.locationManualToggle') }}
      </button>
      <div v-show="manualOpen" class="space-y-2">
        <p class="text-[11px] text-slate-500">{{ t('mktMenu.locationManualHint') }}</p>
        <!-- Paste a map link -->
        <div>
          <label for="mkt-map-link" class="mb-1 block text-[11px] text-slate-400">{{ t('mktMenu.mapLinkLabel') }}</label>
          <div class="flex gap-1.5">
            <input
              id="mkt-map-link"
              v-model.trim="mapLink"
              type="text"
              inputmode="url"
              maxlength="500"
              placeholder="https://maps.google.com/..."
              class="ui-input min-w-0 flex-1"
              :aria-label="t('mktMenu.mapLinkLabel')"
            />
            <button
              type="button"
              class="ui-press shrink-0 rounded-xl border border-slate-600 bg-slate-800/60 px-3 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:text-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
              @click="emit('pasteMapLink')"
            >{{ t('cartPage.pasteLink') }}</button>
          </div>
        </div>
        <!-- Manual latitude / longitude -->
        <div class="grid grid-cols-2 gap-2">
          <label class="block space-y-1">
            <span class="text-[11px] text-slate-400">{{ t('cartPage.latitudeOptional') }}</span>
            <input
              v-model.number="deliveryLat"
              type="number"
              step="any"
              inputmode="decimal"
              placeholder="33.5731"
              class="ui-input"
              :aria-label="t('cartPage.latitudeOptional')"
            />
          </label>
          <label class="block space-y-1">
            <span class="text-[11px] text-slate-400">{{ t('cartPage.longitudeOptional') }}</span>
            <input
              v-model.number="deliveryLng"
              type="number"
              step="any"
              inputmode="decimal"
              placeholder="-7.5898"
              class="ui-input"
              :aria-label="t('cartPage.longitudeOptional')"
            />
          </label>
        </div>
      </div>
    </div>
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
import { ref, computed } from 'vue';
import { useI18n } from '../composables/useI18n';
import AppIcon from './AppIcon.vue';

const { t } = useI18n();

/** The delivery address text (form.delivery_address), two-way. */
const deliveryAddress = defineModel('deliveryAddress', { type: String, default: '' });
/** Whether to save this address after ordering (saveAddressAfterOrder), two-way. */
const saveAddress = defineModel('saveAddress', { type: Boolean, default: false });
/** Optional label for the saved address (saveAddressLabel), two-way. */
const saveAddressLabel = defineModel('saveAddressLabel', { type: String, default: '' });
/** Manual latitude (form.delivery_lat), two-way — the no-GPS fallback. */
const deliveryLat = defineModel('deliveryLat', { type: [Number, String], default: null });
/** Manual longitude (form.delivery_lng), two-way — the no-GPS fallback. */
const deliveryLng = defineModel('deliveryLng', { type: [Number, String], default: null });
/** Pasted / typed map link the parent parses into coordinates, two-way. */
const mapLink = defineModel('mapLink', { type: String, default: '' });

const props = defineProps({
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
  /** Inline validation error for the address field (fieldErrors.delivery_address). */
  addressError: { type: String, default: '' },
  /** Price formatter (fmtPrice). */
  fmtPrice: { type: Function, required: true },
});

// Presentation-only disclosure state for the no-GPS fallback. Auto-opens when the
// parent reports a locate failure so a denied-GPS user immediately sees the way out.
const showManual = ref(false);
const manualOpen = computed(() => showManual.value || !!props.locateError);

const emit = defineEmits(['applyAddress', 'deleteAddress', 'locate', 'pasteMapLink']);
</script>
