<template>
  <div
    class="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5"
    role="alert"
  >
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden="true"><path d="M8 2 1.5 13h13L8 2Zm0 4v3.5M8 11.5h.01"/></svg>
    <p class="min-w-0 flex-1 text-[11px] leading-snug text-amber-300">{{ t('waiterPage.tableStatusStale') }}</p>
  </div>
</template>

<script setup>
// The stale-table-statuses warning of WaiterPage.vue's floor view, extracted as a
// STATIC presentational child (RISK FE-2). It tells the waiter the last table-poll
// failed and will retry automatically. Pure display: no props/state/emits — the
// parent (WaiterPage.vue) owns the `tableStatusesStale` flag and keeps the
// mounting v-if; this just renders the fixed warning copy.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();
</script>
