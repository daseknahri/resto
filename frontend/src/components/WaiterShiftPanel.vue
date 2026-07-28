<template>
  <div
    id="waiter-panel-shift"
    role="tabpanel"
    aria-labelledby="waiter-tab-shift"
    class="space-y-4 ui-reveal"
  >
    <!-- Shift start picker -->
    <div class="flex flex-wrap items-end gap-3">
      <div class="min-w-0 flex-1 space-y-1 sm:flex-none">
        <label class="ui-stat-label block" for="shift-since-input">{{ t('waiterPage.shiftSince') }}</label>
        <input
          id="shift-since-input"
          v-model="since"
          type="datetime-local"
          :aria-label="t('waiterPage.shiftSince')"
          class="ui-input"
        />
      </div>
      <button
        class="ui-btn-outline ui-press ui-touch-target disabled:opacity-50"
        :disabled="waiter.shiftSummaryLoading"
        @click="emit('refresh')"
      >
        {{ waiter.shiftSummaryLoading ? t('waiterPage.shiftLoading') : t('waiterPage.shiftRefresh') }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="waiter.shiftSummaryError" class="flex items-start gap-2 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
      <p class="flex-1 text-sm text-red-300">{{ waiter.shiftSummaryError }}</p>
    </div>

    <!-- Stats grid -->
    <div v-else-if="waiter.shiftSummary" class="grid gap-3" :class="showShiftRevenue ? 'grid-cols-3' : 'grid-cols-2'">
      <div class="ui-stat-tile space-y-1.5 text-center">
        <p class="ui-stat-value tabular-nums text-2xl font-bold">{{ waiter.shiftSummary.orders_handled }}</p>
        <p class="ui-stat-label">{{ t('waiterPage.shiftOrders') }}</p>
      </div>
      <div v-if="showShiftRevenue" class="ui-stat-tile space-y-1.5 text-center">
        <p class="ui-stat-value tabular-nums text-2xl font-bold text-emerald-300">{{ shiftRevenue }}</p>
        <p class="ui-stat-label">{{ t('waiterPage.shiftRevenue') }}</p>
      </div>
      <div class="ui-stat-tile space-y-1.5 text-center">
        <p class="ui-stat-value tabular-nums text-2xl font-bold text-sky-300">
          {{ waiter.shiftSummary.average_prep_time_minutes != null ? waiter.shiftSummary.average_prep_time_minutes : '—' }}<span v-if="waiter.shiftSummary.average_prep_time_minutes != null" class="text-base font-normal text-sky-400/70">m</span>
        </p>
        <p class="ui-stat-label">{{ t('waiterPage.shiftAvgPrep') }}</p>
      </div>
    </div>

    <!-- Period caption -->
    <p v-if="waiter.shiftSummary" class="text-center text-xs text-slate-500 tabular-nums">
      {{ t('waiterPage.shiftPeriod', { hours: waiter.shiftSummary.period_hours }) }}
    </p>

    <!-- Skeleton while loading shift summary -->
    <div v-else-if="waiter.shiftSummaryLoading" class="grid grid-cols-2 gap-3" aria-busy="true" :aria-label="t('common.loading')">
      <div v-for="i in 2" :key="i" class="ui-skeleton h-20 rounded-2xl" />
    </div>

    <!-- Empty state: no data yet (before first date filter is applied) -->
    <div v-else class="ui-empty-state py-8 text-center">
      <p class="text-sm text-slate-400">{{ t('waiterPage.shiftHint') }}</p>
    </div>

    <!-- Change password -->
    <details class="group rounded-2xl border border-slate-700/50 bg-slate-800/30">
      <summary class="flex cursor-pointer select-none items-center justify-between gap-2 px-4 py-3 text-sm font-medium text-slate-300 hover:text-slate-100">
        {{ t('staffPassword.title') }}
        <svg aria-hidden="true" class="h-4 w-4 shrink-0 transition-transform group-open:rotate-180" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd"/></svg>
      </summary>
      <form class="space-y-3 px-4 pb-4" @submit.prevent="emit('submitPassword')">
        <div class="space-y-1">
          <label class="ui-stat-label block" for="waiter-current-password">{{ t('staffPassword.currentLabel') }}</label>
          <input
            id="waiter-current-password"
            v-model="pwForm.current"
            type="password"
            autocomplete="current-password"
            class="ui-input"
            :disabled="pwForm.loading"
          />
        </div>
        <div class="space-y-1">
          <label class="ui-stat-label block" for="waiter-new-password">{{ t('staffPassword.newLabel') }}</label>
          <input
            id="waiter-new-password"
            v-model="pwForm.next"
            type="password"
            autocomplete="new-password"
            class="ui-input"
            :disabled="pwForm.loading"
          />
        </div>
        <p v-if="pwForm.error" class="text-xs text-red-400" role="alert">{{ pwForm.error }}</p>
        <button
          type="submit"
          class="ui-btn-primary ui-touch-target w-full justify-center disabled:opacity-50"
          :disabled="pwForm.loading || !pwForm.current || !pwForm.next"
        >
          {{ pwForm.loading ? t('staffPassword.submitting') : t('staffPassword.submitBtn') }}
        </button>
      </form>
    </details>
  </div>
</template>

<script setup>
// Shift summary + change-password tab panel of WaiterPage.vue, extracted as a
// standalone child (RISK FE-2). It renders the shift-since picker, the shift-summary
// stats (orders handled / revenue / avg prep) with error/loading/empty states, and
// the change-password form. The parent (WaiterPage.vue) keeps the `waiter` store, the
// summary fetch (loadShiftSummary) and the password submit (submitPasswordChange); the
// two form values round-trip via `v-model:since` / `v-model:pw-form` (defineModel), and
// the panel forwards intent via `refresh` / `submitPassword` emits. The
// `activeTab === 'shift'` v-else-if gate stays in the parent's tab-panel chain.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const since = defineModel('since', { type: String, default: '' });
const pwForm = defineModel('pwForm', { type: Object, required: true });

defineProps({
  /** The waiter store (shiftSummary / shiftSummaryLoading / shiftSummaryError). */
  waiter: { type: Object, required: true },
  /** Whether to show the revenue tile (shiftSummary.show_revenue). */
  showShiftRevenue: { type: Boolean, default: false },
  /** Pre-formatted shift revenue string. */
  shiftRevenue: { type: String, default: '' },
});

const emit = defineEmits(['refresh', 'submitPassword']);
</script>
