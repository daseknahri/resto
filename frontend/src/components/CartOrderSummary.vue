<template>
  <!-- ── Order summary breakdown ── -->
  <div class="border-t border-slate-800/50 pt-3 space-y-2 text-xs">
    <div v-if="fulfillmentType === 'delivery' && deliveryFeeAmount > 0" class="flex items-center justify-between text-slate-400">
      <span>{{ t('cartPage.subtotal') }}</span>
      <span class="tabular-nums font-medium">{{ formatPrice(subtotal) }}</span>
    </div>
    <div v-if="loyaltyDiscount > 0" class="flex items-center justify-between text-amber-300">
      <span>{{ t('cartPage.loyaltyDiscount') }}</span>
      <span class="tabular-nums font-semibold">-{{ formatPrice(loyaltyDiscount) }}</span>
    </div>
    <div v-if="fulfillmentType === 'delivery' && deliveryFeeAmount > 0" class="flex items-center justify-between text-slate-300">
      <span>
        {{ t('cartPage.deliveryFee') }}
        <span v-if="deliveryFeeIsDistance" class="text-[11px] text-slate-500">· {{ deliveryDistanceKm }} km</span>
      </span>
      <span class="tabular-nums font-medium">{{ formatPrice(deliveryFeeAmount) }}</span>
    </div>
    <div v-if="fulfillmentType === 'delivery' && deliveryFeePending" class="flex items-center justify-between text-slate-400">
      <span>{{ t('cartPage.deliveryFee') }}</span>
      <span class="text-[11px]">{{ t('cartPage.deliveryFeeByDistanceShort') }}</span>
    </div>
    <div v-else-if="fulfillmentType === 'delivery' && !deliveryOutOfRange && deliveryFeeAmount === 0" class="flex items-center justify-between text-emerald-400">
      <span>{{ t('cartPage.deliveryFee') }}</span>
      <span class="font-semibold">{{ t('cartPage.free') }}</span>
    </div>
    <div v-if="tipAmount > 0" class="flex items-center justify-between text-[var(--color-secondary)]/75">
      <span>{{ t('cartPage.tipLabel') }}</span>
      <span class="tabular-nums font-medium">+{{ formatPrice(tipAmount) }}</span>
    </div>
    <div v-if="walletApplied && walletDeduction > 0" class="flex items-center justify-between text-emerald-400">
      <span>{{ t('cartPage.payWithCredits') }}</span>
      <span class="tabular-nums font-semibold">-{{ formatPrice(walletDeduction) }}</span>
    </div>
    <div class="flex items-center justify-between pt-2 border-t border-slate-700/50">
      <span class="text-sm font-bold text-slate-200 tracking-tight">{{ t('cartPage.total') }}</span>
      <span class="text-xl font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(grandTotal) }}</span>
    </div>
    <!-- Pre-order ETA: a time estimate shown BEFORE the customer pays -->
    <div
      v-if="checkoutEta && !deliveryOutOfRange"
      class="flex items-center gap-1.5 pt-1 text-sky-300"
    >
      <AppIcon name="clock" class="h-3.5 w-3.5 shrink-0" />
      <span class="font-medium">
        {{ checkoutEta.type === 'delivery'
          ? t('cartPage.etaDelivery', { min: checkoutEta.min, max: checkoutEta.max })
          : t('menu.etaReadyIn', { min: checkoutEta.min, max: checkoutEta.max }) }}
      </span>
    </div>
  </div>
</template>

<script setup>
// Order-summary breakdown of Cart.vue's checkout panel, extracted as a standalone
// presentational child (RISK FE-2). DISPLAY ONLY: it renders the subtotal / loyalty
// discount / delivery-fee (distance/pending/free/flat) / tip / wallet-credit rows,
// the grand total, and the pre-order ETA. It computes NOTHING and mutates NOTHING —
// every pricing value is computed in the parent (Cart.vue owns the whole pricing +
// place-order flow) and passed in as a prop; `formatPrice` is a function prop so
// currency formatting stays single-sourced. No payment, no order placement here.
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** 'delivery' | 'pickup' | 'table' — gates the delivery-fee rows. */
  fulfillmentType: { type: String, default: '' },
  /** Cart subtotal (cart.total) — shown when a delivery fee applies. */
  subtotal: { type: [Number, String], default: 0 },
  /** Delivery fee amount (0 = free). */
  deliveryFeeAmount: { type: Number, default: 0 },
  /** Whether the delivery fee is distance-based (shows the km hint). */
  deliveryFeeIsDistance: { type: Boolean, default: false },
  /** Delivery distance in km (for the distance hint). */
  deliveryDistanceKm: { type: [Number, String], default: 0 },
  /** Whether the delivery fee is still pending (distance not yet known). */
  deliveryFeePending: { type: Boolean, default: false },
  /** Whether the delivery address is out of range. */
  deliveryOutOfRange: { type: Boolean, default: false },
  /** Loyalty discount applied (0 = none). */
  loyaltyDiscount: { type: Number, default: 0 },
  /** Tip amount (0 = none). */
  tipAmount: { type: Number, default: 0 },
  /** Whether wallet credit is being applied. */
  walletApplied: { type: Boolean, default: false },
  /** Wallet credit deducted from the total. */
  walletDeduction: { type: Number, default: 0 },
  /** The grand total to charge (orderGrandTotal). */
  grandTotal: { type: [Number, String], default: 0 },
  /** Pre-order ETA ({ type, min, max }) or null. */
  checkoutEta: { type: Object, default: null },
  /** Currency formatter (amount) => string, owned by the parent. */
  formatPrice: { type: Function, required: true },
});
</script>
