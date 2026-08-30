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
// extracted as a standalone presentational child (RISK FE-2).
//
// PERF (H-2): this component OWNS the 1-second countdown timer. It used to live in
// the parent page as a `flashSaleCountdown` ref read in the parent template, so the
// whole menu page (~150 dishes, each re-running its price formatter) re-ran its
// render function once a second while a flash sale was live — i.e. during peak
// traffic, often on slow devices. Ticking the countdown ref *here* confines the
// per-second re-render to this tiny banner. When the sale reaches 0 we emit `ended`
// so the parent can drop `restaurant.flash_sale` — that reverts the per-dish price
// badges and the checkout discount exactly as the old inline countdown did — and the
// parent no longer holds any per-second ref.
import { ref, watch, onBeforeUnmount } from 'vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const props = defineProps({
  /** The active flash sale ({ discount_pct, active_until, ... }); non-null (parent gates on it). */
  flashSale: { type: Object, required: true },
});

// `ended` fires once the countdown crosses 0 so the parent can clear the sale.
const emit = defineEmits(['ended']);

// Pre-formatted countdown string ("Hh MMm" or "MM:SS"); '' until the timer produces one.
const countdown = ref('');
let _timer = null;

const tick = () => {
  const activeUntil = props.flashSale?.active_until;
  if (!activeUntil) { countdown.value = ''; return; }
  const diff = new Date(activeUntil) - Date.now();
  if (diff <= 0) {
    countdown.value = '';
    emit('ended');   // parent drops flash_sale → this banner unmounts (onBeforeUnmount clears the timer)
    return;
  }
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  if (h >= 24) { countdown.value = ''; return; } // keep ticking; show nothing until < 24h out
  countdown.value = h > 0
    ? `${h}h ${String(m).padStart(2, '0')}m`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
};

// Restart the 1s ticker whenever the sale's end timestamp changes (and on mount).
watch(
  () => props.flashSale?.active_until,
  (activeUntil) => {
    clearInterval(_timer);
    _timer = null;
    if (activeUntil) {
      tick();
      _timer = setInterval(tick, 1000);
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  clearInterval(_timer);
  _timer = null;
});
</script>
