<template>
  <!-- Loyalty redemption -->
  <label
    v-if="available"
    class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3"
  >
    <input v-model="useLoyalty" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-amber-500 focus:ring-amber-500/40" />
    <span class="flex-1 text-xs text-amber-200">{{ t('mktMenu.loyaltyRedeem', { points }) }}</span>
    <span v-if="useLoyalty && discount > 0" class="text-xs font-semibold tabular-nums text-amber-300">-{{ fmtPrice(discount) }}</span>
  </label>
  <!-- ── Loyalty earn projection ── -->
  <p
    v-if="earnEnabled && earnProjection > 0"
    class="text-[11px] text-violet-400/80 ps-1"
  >{{ t('mktMenu.loyaltyEarnProjection', { points: earnProjection }) }}</p>
</template>

<script setup>
// The loyalty redeem toggle + earn-projection line of MarketplaceMenuPage.vue's
// checkout drawer, extracted as a small FRAGMENT child (RISK FE-2) — sub-part 4 of
// the checkout-drawer split. `useLoyalty` (whether to redeem points) is a two-way
// model; everything else is derived in the parent (whether redemption is available,
// the point balance, the discount it buys, and the earn projection) and passed as
// props, so the parent keeps all the loyalty math + the order effect. No logic here.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

/** Whether the customer chose to redeem points (useLoyalty), two-way. */
const useLoyalty = defineModel('useLoyalty', { type: Boolean, default: false });

defineProps({
  /** Whether redemption is offered at all (loyaltyAvailable). */
  available: { type: Boolean, default: false },
  /** The customer's redeemable point balance (loyaltyPoints). */
  points: { type: Number, default: 0 },
  /** Money discount the redeemed points buy (loyaltyDiscount). */
  discount: { type: Number, default: 0 },
  /** Whether earning points is enabled (loyaltyConfig.enabled). */
  earnEnabled: { type: Boolean, default: false },
  /** Points this order would earn (loyaltyEarnProjection). */
  earnProjection: { type: Number, default: 0 },
  /** Price formatter (fmtPrice). */
  fmtPrice: { type: Function, required: true },
});
</script>
