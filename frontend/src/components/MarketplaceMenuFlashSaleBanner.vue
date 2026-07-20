<template>
  <!-- Flash sale banner -->
  <div
    class="ui-reveal mx-4 mb-2 flex items-center justify-between gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-sm"
    :style="{ '--ui-delay': '40ms' }"
    role="status"
  >
    <p class="font-semibold text-amber-200">
      {{ t('mktMenu.flashSaleBanner', { pct: flashSale.discount_pct }) }}
    </p>
    <p v-if="countdown" class="shrink-0 font-mono text-[11px] tabular-nums text-amber-300/80">
      {{ t('mktMenu.flashSaleEnds', { time: countdown }) }}
    </p>
  </div>
</template>

<script setup>
// Flash-sale banner of MarketplaceMenuPage.vue (customer menu-browsing page),
// extracted as a standalone presentational child (RISK FE-2). Display only: it
// shows the active flash-sale discount percentage and, when a countdown string
// is supplied, the time remaining. The `restaurant.flash_sale` render gate stays
// in the parent (which conditionally renders this component, so `flashSale` is
// always present here), and the parent keeps ownership of the countdown timer
// (`flashSaleCountdown` / updateFlashSaleCountdown) — this component only renders
// the current value it's handed. No API calls, no emits, mutates nothing.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The active flash sale ({ discount_pct, ... }); non-null (parent gates on it). */
  flashSale: { type: Object, required: true },
  /** Pre-formatted countdown string ("mm:ss"); empty until the timer produces one. */
  countdown: { type: String, default: '' },
});
</script>
