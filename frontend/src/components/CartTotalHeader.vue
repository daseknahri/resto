<template>
  <!-- Compact total header -->
  <div class="flex items-center justify-between gap-3 rounded-xl bg-slate-900/60 px-4 py-3.5 border border-slate-800/60">
    <div>
      <p class="text-[10px] font-medium uppercase tracking-widest text-slate-500">{{ t('cartPage.total') }}</p>
      <p class="text-3xl font-bold tabular-nums leading-tight text-[var(--color-secondary)]">
        {{ formatPrice(grandTotal) }}
      </p>
    </div>
    <div class="text-end text-[11px] text-slate-500 space-y-0.5">
      <p class="font-medium text-slate-400">{{ countLabel }}</p>
      <p v-if="fulfillmentType" class="capitalize text-slate-400">
        {{ fulfillmentType === 'delivery' ? t('cartPage.delivery') : t('cartPage.pickup') }}
      </p>
    </div>
  </div>
</template>

<script setup>
// Compact total header of Cart.vue's checkout panel, extracted as a standalone
// presentational child (RISK FE-2). DISPLAY ONLY: the big grand-total figure, the
// item-count label, and the fulfillment type. It computes and mutates nothing —
// the grand total is computed in the parent (Cart.vue owns the pricing flow) and
// passed as a prop; `formatPrice` is a function prop. No payment or order placement.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The grand total to display (orderGrandTotal). */
  grandTotal: { type: [Number, String], default: 0 },
  /** Pre-formatted item-count label (itemCountLabel(cart.count)). */
  countLabel: { type: String, default: '' },
  /** 'delivery' | 'pickup' | 'table' — shown as a caption, or '' to hide. */
  fulfillmentType: { type: String, default: '' },
  /** Currency formatter (amount) => string, owned by the parent. */
  formatPrice: { type: Function, required: true },
});
</script>
