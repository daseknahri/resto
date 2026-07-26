<template>
  <!-- Totals -->
  <div class="ui-panel px-4 py-3 space-y-1.5 text-sm">
    <!-- ETA chip — shown above totals when available -->
    <div v-if="prepEta" class="flex items-center gap-1.5 text-[11px] text-emerald-400/80 pb-0.5">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 shrink-0" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="M8 4.75V8l2.25 2"/></svg>
      {{ t('menu.etaReadyIn', { min: prepEta.min, max: prepEta.max }) }}
    </div>
    <div class="flex justify-between text-slate-400">
      <span>{{ t('mktMenu.subtotal') }}</span>
      <span class="tabular-nums">{{ fmtPrice(cartTotal) }}</span>
    </div>
    <div v-if="fulfillmentType === 'delivery'" class="flex justify-between text-slate-400">
      <span>
        {{ t('mktMenu.deliveryFeeLabel') }}
        <span v-if="deliveryFeeIsDistance" class="text-[11px] text-slate-500 tabular-nums">· {{ deliveryDistanceKm }} km</span>
      </span>
      <span class="tabular-nums">{{ deliveryIsFree ? t('mktMenu.freeDelivery') : fmtPrice(deliveryFee) }}</span>
    </div>
    <div v-if="flashSaleDiscount > 0" class="flex justify-between text-amber-300">
      <span>{{ t('mktMenu.flashDiscount', { pct: flashSalePct }) }}</span>
      <span class="tabular-nums">-{{ fmtPrice(flashSaleDiscount) }}</span>
    </div>
    <div v-if="loyaltyDiscount > 0" class="flex justify-between text-amber-300">
      <span>{{ t('mktMenu.loyaltyDiscount') }}</span>
      <span class="tabular-nums">-{{ fmtPrice(loyaltyDiscount) }}</span>
    </div>
    <div class="flex justify-between font-bold text-white border-t border-slate-800 pt-1.5 mt-1.5">
      <span>{{ t('mktMenu.total') }}</span>
      <span class="tabular-nums">{{ fmtPrice(orderTotal) }}</span>
    </div>
  </div>
</template>

<script setup>
// The order-totals panel of MarketplaceMenuPage.vue's checkout drawer, extracted as a
// DISPLAY-ONLY child (RISK FE-2). It shows the prep-time ETA chip, subtotal, the
// delivery fee (distance / free / flat), flash-sale + loyalty discount lines, and the
// grand total. It computes NOTHING and mutates NOTHING — every value is derived in
// the parent (cartTotal / deliveryFee / flashSaleDiscount / loyaltyDiscount /
// orderTotal / prepEta) and passed as a prop.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Prep-time estimate ({ min, max }) or null (prepEta). */
  prepEta: { type: Object, default: null },
  /** Cart subtotal (cartTotal). */
  cartTotal: { type: Number, default: 0 },
  /** Fulfillment type (form.fulfillment_type) — gates the delivery-fee row. */
  fulfillmentType: { type: String, default: 'pickup' },
  /** Whether the delivery fee is distance-based (deliveryFeeIsDistance). */
  deliveryFeeIsDistance: { type: Boolean, default: false },
  /** Resolved distance in km (deliveryDistanceKm). */
  deliveryDistanceKm: { type: [Number, String], default: 0 },
  /** Whether delivery is free (deliveryIsFree). */
  deliveryIsFree: { type: Boolean, default: false },
  /** Delivery fee (deliveryFee). */
  deliveryFee: { type: Number, default: 0 },
  /** Flash-sale discount amount (flashSaleDiscount). */
  flashSaleDiscount: { type: Number, default: 0 },
  /** Flash-sale percent (restaurant.flash_sale.discount_pct) for the label. */
  flashSalePct: { type: [Number, String], default: 0 },
  /** Loyalty discount amount (loyaltyDiscount). */
  loyaltyDiscount: { type: Number, default: 0 },
  /** Grand total (orderTotal). */
  orderTotal: { type: Number, default: 0 },
  /** Price formatter (fmtPrice). */
  fmtPrice: { type: Function, required: true },
});
</script>
