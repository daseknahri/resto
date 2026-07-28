<template>
  <div class="ui-panel p-4 space-y-3 ui-reveal">
    <button
      class="flex w-full items-center justify-between gap-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
      :aria-expanded="show"
      aria-controls="driver-ride-history-panel"
      @click="emit('toggle')"
    >
      <p class="text-sm font-semibold text-slate-200">{{ t('driverRides.historyTitle') }}</p>
      <AppIcon :name="show ? 'chevronUp' : 'chevronDown'" class="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
    </button>
    <div id="driver-ride-history-panel">
      <template v-if="show">
        <div v-if="loading && !items.length" class="space-y-2" aria-busy="true">
          <div v-for="i in 3" :key="i" class="ui-skeleton h-12" />
        </div>
        <div v-else-if="!items.length" class="ui-empty-state text-center py-4 space-y-1">
          <p class="text-sm font-semibold text-slate-100">{{ t('driverRides.historyEmpty') }}</p>
        </div>
        <ul v-else class="space-y-2">
          <li
            v-for="(r, index) in items"
            :key="r.id"
            class="ui-reveal rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 space-y-1"
            :style="{ '--ui-delay': `${Math.min(index, 9) * 20}ms` }"
          >
            <div class="flex items-start justify-between gap-3">
              <p class="truncate text-sm text-slate-200" :title="r.dropoff_address"><span v-if="r.kind === 'package'" aria-hidden="true">📦 </span>{{ r.dropoff_address }}</p>
              <div class="flex shrink-0 items-center gap-1.5">
                <span
                  v-if="r.payment_method === 'cash'"
                  class="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-300"
                >{{ t('driverRides.collectCash', { amount: fmtMoney(r.fare) }) }}</span>
                <span
                  v-else
                  class="rounded-full bg-emerald-500/12 px-2 py-0.5 text-[11px] font-semibold text-emerald-300"
                >{{ t('driverRides.paidWallet') }}</span>
                <span class="text-sm font-bold tabular-nums text-emerald-300">{{ fmtMoney(r.fare) }}</span>
              </div>
            </div>
            <div class="flex items-center gap-3 text-[11px] text-slate-500">
              <span>{{ fmtDate(r.completed_at) }}</span>
              <span v-if="r.driver_rider_rating != null" class="flex items-center gap-0.5 text-amber-400">
                <span aria-hidden="true">★</span>
                <span>{{ r.driver_rider_rating }}</span>
              </span>
            </div>
          </li>
        </ul>
      </template>
    </div>
  </div>
</template>

<script setup>
// Ride history (the driver's completed/cancelled rides) accordion of
// DriverPage.vue, extracted as a standalone presentational child (RISK FE-2),
// mirroring the merged DriverPageDeliveryHistory.vue / DriverPageCashoutHistory.vue
// precedents. Fetch state and the lazy-load-on-first-expand behaviour stay in the
// parent (DriverPage.vue) — this component only renders whatever history the
// parent has loaded so far, and asks the parent to toggle the accordion via the
// `toggle` emit. The car-only visibility gate (driverVehicleType === 'car') also
// stays in the parent, which conditionally renders this component. `fmtDate` /
// `fmtMoney` are passed down as functions (same convention as the sibling history
// precedents) so formatting stays single-sourced in the parent rather than
// duplicated here. This block only DISPLAYS ride fares — it makes no API calls
// and mutates nothing.
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Whether the accordion is expanded. */
  show: { type: Boolean, default: false },
  /** True while the parent is fetching ride history. */
  loading: { type: Boolean, default: false },
  /** The driver's completed/cancelled rides loaded so far. */
  items: { type: Array, default: () => [] },
  /** Locale-aware date formatter, owned by the parent. */
  fmtDate: { type: Function, required: true },
  /** Locale-aware currency formatter, owned by the parent. */
  fmtMoney: { type: Function, required: true },
});

const emit = defineEmits(['toggle']);
</script>
