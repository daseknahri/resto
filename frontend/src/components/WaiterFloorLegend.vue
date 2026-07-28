<template>
  <details class="group rounded-xl border border-slate-700/40 bg-slate-800/30 px-3 py-2 text-xs text-slate-400">
    <summary class="cursor-pointer select-none list-none font-medium text-slate-300 [&::-webkit-details-marker]:hidden">
      <span aria-hidden="true">ⓘ</span> {{ t('waiterPage.floorLegend') }}
    </summary>
    <ul class="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-4">
      <li class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-400"></span>{{ t('waiterPage.floorStatusOpen') }}</li>
      <li class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 shrink-0 rounded-full bg-amber-400"></span>{{ t('waiterPage.floorStatusOccupied') }}</li>
      <li class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 shrink-0 rounded-full bg-rose-400"></span>{{ t('waiterPage.floorStatusDirty') }}</li>
      <li class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 shrink-0 rounded-full bg-violet-400"></span>{{ t('waiterPage.floorStatusReserved') }}</li>
    </ul>
  </details>
</template>

<script setup>
// The floor-map status legend of WaiterPage.vue, extracted as a STATIC
// presentational child (RISK FE-2). A collapsed <details> that explains the four
// table-status dot colours (open / occupied / dirty / reserved). Pure display: no
// props, no state, no emits — it only renders i18n copy, so lifting it just
// declutters the parent's floor-view template.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();
</script>
