<template>
  <div class="ui-panel p-4 space-y-3 ui-reveal">
    <button
      class="flex w-full items-center justify-between gap-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400"
      :aria-expanded="show"
      aria-controls="driver-cashout-history-panel"
      @click="emit('toggle')"
    >
      <p class="text-sm font-semibold text-slate-200">{{ t('driver.cashOutHistoryTitle') }}</p>
      <AppIcon :name="show ? 'chevronUp' : 'chevronDown'" class="h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
    </button>
    <div id="driver-cashout-history-panel">
      <template v-if="show">
        <div v-if="loading && !items.length" class="space-y-2" aria-busy="true">
          <div v-for="i in 3" :key="i" class="ui-skeleton h-12" />
        </div>
        <div v-else-if="!items.length" class="ui-empty-state text-center py-4 space-y-1">
          <p class="text-sm font-semibold text-slate-100">{{ t('driver.cashOutHistoryEmpty') }}</p>
        </div>
        <ul v-else class="space-y-2">
          <li
            v-for="(c, index) in items"
            :key="c.id"
            class="ui-reveal flex items-center justify-between gap-3 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5"
            :style="{ '--ui-delay': `${Math.min(index, 9) * 20}ms` }"
          >
            <div class="min-w-0">
              <p class="truncate text-sm text-slate-200">{{ c.settled_by || t('driver.cashOutHistoryUnsettled') }}</p>
              <p class="text-[11px] text-slate-500">{{ fmtDate(c.resolved_at || c.created_at) }}</p>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <span
                class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
                :class="{
                  'bg-emerald-500/15 text-emerald-300': c.status === 'paid',
                  'bg-slate-700/60 text-slate-400': c.status === 'cancelled',
                  'bg-red-500/15 text-red-300': c.status === 'expired',
                }"
              >{{ t(`driver.cashOutStatus_${c.status}`) }}</span>
              <span class="text-sm font-semibold tabular-nums" :class="c.status === 'paid' ? 'text-emerald-300' : 'text-slate-500'">{{ fmtMoney(c.amount) }}</span>
            </div>
          </li>
        </ul>
        <button
          v-if="hasMore"
          :disabled="loading"
          class="mt-2 w-full rounded-xl border border-slate-700/50 bg-slate-800/50 py-2.5 text-sm font-medium text-slate-400 transition hover:border-slate-600 hover:text-slate-200 disabled:opacity-40"
          @click="emit('load-more')"
        >{{ loading ? t('common.loading') : t('driver.historyLoadMore') }}</button>
      </template>
    </div>
  </div>
</template>

<script setup>
// Cash-out history (resolved requests: paid / cancelled / expired) accordion of
// DriverPage.vue, extracted as a standalone presentational child (RISK FE-2),
// mirroring the merged DriverPageDeliveryHistory.vue precedent. Fetch/pagination
// state and the lazy-load-on-first-expand behaviour all stay in the parent
// (DriverPage.vue) — this component only renders whatever page of history the
// parent has loaded so far, and asks the parent to toggle the accordion / load
// another page via emits. `fmtDate` / `fmtMoney` are passed down as functions
// (same convention as the delivery-history precedent) so formatting stays
// single-sourced in the parent rather than duplicated here.
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Whether the accordion is expanded. */
  show: { type: Boolean, default: false },
  /** True while the parent is fetching a page of cash-out history. */
  loading: { type: Boolean, default: false },
  /** Resolved cash-out requests loaded so far (across pages). */
  items: { type: Array, default: () => [] },
  /** True when another page is available via the `load-more` emit. */
  hasMore: { type: Boolean, default: false },
  /** Locale-aware date formatter, owned by the parent. */
  fmtDate: { type: Function, required: true },
  /** Locale-aware currency formatter, owned by the parent. */
  fmtMoney: { type: Function, required: true },
});

const emit = defineEmits(['toggle', 'load-more']);
</script>
