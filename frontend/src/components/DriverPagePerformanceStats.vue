<template>
  <!-- Driver performance stats strip (avg rating / acceptance / completion) -->
  <div
    class="ui-panel grid grid-cols-3 divide-x divide-slate-700/40 p-0 overflow-hidden ui-reveal"
    :aria-label="t('driver.statsCard')"
  >
    <div class="flex flex-col items-center justify-center px-3 py-3.5 text-center">
      <p class="ui-stat-label">{{ t('driver.avgRating') }}</p>
      <p class="mt-1 text-base font-bold text-amber-300">
        {{ earnings.avg_rating != null ? `★ ${earnings.avg_rating}` : '—' }}
      </p>
    </div>
    <div class="flex flex-col items-center justify-center px-3 py-3.5 text-center">
      <p class="ui-stat-label">{{ t('driver.acceptanceRate') }}</p>
      <p class="mt-1 text-base font-bold tabular-nums text-slate-200">
        {{ earnings.acceptance_rate != null ? `${earnings.acceptance_rate}%` : '—' }}
      </p>
    </div>
    <div class="flex flex-col items-center justify-center px-3 py-3.5 text-center">
      <p class="ui-stat-label">{{ t('driver.completionRate') }}</p>
      <p class="mt-1 text-base font-bold tabular-nums text-emerald-400">
        {{ earnings.completion_rate != null ? `${earnings.completion_rate}%` : '—' }}
      </p>
    </div>
  </div>
</template>

<script setup>
// Driver performance stats strip (avg rating / acceptance rate / completion
// rate) of DriverPage.vue, extracted as a standalone presentational child
// (RISK FE-2), mirroring the sibling DriverPageRideHistory.vue precedent. This
// is DISPLAY ONLY — it renders the three headline figures from the driver's
// `earnings` summary and nothing else: no API calls, no emits, and it mutates
// nothing (no money/wallet/cash-out/order logic). The
// `earnings && earnings.total_deliveries > 0` render gate stays in the parent
// (DriverPage.vue), which conditionally renders this component and owns the
// `earnings` fetch, so `earnings` is always present here. No formatter props are
// needed — the values are rendered inline exactly as the original strip did
// (raw rating with a leading star, or a percentage, with an em-dash fallback).
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The driver's earnings/performance summary (avg_rating, acceptance_rate, completion_rate). */
  earnings: { type: Object, required: true },
});
</script>
