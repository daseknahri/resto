<template>
  <article
    class="ui-panel ui-reveal flex items-center justify-between gap-3 p-4"
    :style="{ '--ui-delay': `${Math.min(index, 5) * 24}ms` }"
  >
    <div class="min-w-0 space-y-0.5">
      <div class="flex flex-wrap items-center gap-2 min-w-0">
        <span class="truncate text-sm font-semibold text-white" :title="sale.name">{{ sale.name }}</span>
        <span class="ui-chip tabular-nums text-amber-300">−{{ sale.discount_value }}%</span>
        <span v-if="sale.is_live" class="ui-status-pill border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
          <span class="ui-live-dot bg-emerald-400" aria-hidden="true" />
          {{ t('adminFlashSales.live') }}
        </span>
      </div>
      <p v-if="sale.description" class="truncate text-xs text-slate-400" :title="sale.description">{{ sale.description }}</p>
      <p class="text-[11px] tabular-nums text-slate-500">
        {{ t('ownerPromotions.flashUntil', { date: fmtFlashDate(sale.active_until) }) }}
      </p>
    </div>
    <button
      class="ui-btn-outline ui-press ui-touch-target shrink-0 inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold transition-colors disabled:opacity-50"
      :class="sale.opted_in
        ? 'border-emerald-500/40 text-emerald-300 hover:border-red-400/40 hover:text-red-300'
        : 'hover:border-amber-400/50 hover:text-amber-300'"
      :disabled="busy"
      :aria-pressed="sale.opted_in"
      :aria-label="`${sale.opted_in ? t('ownerPromotions.flashOptOut') : t('ownerPromotions.flashOptIn')} ${sale.name}`"
      @click="emit('toggle', sale)"
    >
      <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
      {{ busy ? t('common.loading') : (sale.opted_in ? t('ownerPromotions.flashOptOut') : t('ownerPromotions.flashOptIn')) }}
    </button>
  </article>
</template>

<script setup>
// A single platform flash-sale opt-in card from OwnerPromotions.vue, extracted
// as a standalone presentational child (RISK FE-2). Display only: it renders one
// platform flash sale (name, discount, live badge, description, end date) and an
// opt-in/opt-out button that forwards intent to the parent via the `toggle` emit
// (with the sale). The parent keeps the flash-sales list, the opt-in API mutation
// (toggleFlashOptIn) and the in-flight flashBusyId guard (passed back as `busy`).
// `fmtFlashDate` is a function prop so date formatting stays single-sourced in the
// parent; `index` drives the same staggered reveal the inline v-for used. No API
// calls or store access here.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The platform flash sale to render ({ name, discount_value, is_live, description, active_until, opted_in }). */
  sale: { type: Object, required: true },
  /** Row index within the list — drives the staggered --ui-delay reveal. */
  index: { type: Number, default: 0 },
  /** Formatter (active_until) => string for the "until" line. */
  fmtFlashDate: { type: Function, required: true },
  /** True while this sale's opt-in/opt-out request is in flight. */
  busy: { type: Boolean, default: false },
});

const emit = defineEmits(['toggle']);
</script>
