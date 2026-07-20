<template>
  <article
    class="ui-panel ui-surface-lift ui-reveal p-4 flex items-start justify-between gap-4"
    :style="{ '--ui-delay': `${Math.min(index, 9) * 24}ms` }"
  >
    <div class="flex-1 min-w-0 space-y-1">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="text-sm font-semibold text-white leading-snug">{{ rule.name }}</span>
        <span
          class="ui-status-pill shrink-0 inline-flex items-center gap-1"
          :class="rule.is_active
            ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
            : 'border-slate-600/60 bg-slate-700/30 text-slate-400'"
        >
          <span class="h-1.5 w-1.5 rounded-full shrink-0" :class="rule.is_active ? 'bg-emerald-400' : 'bg-slate-500'" aria-hidden="true" />
          {{ rule.is_active ? t('happyHour.activeNow') : t('happyHour.inactive') }}
        </span>
        <span class="ui-chip tabular-nums text-emerald-300">-{{ rule.percent_off }}%</span>
      </div>
      <p class="text-xs text-slate-400 tabular-nums">{{ rule.start_time }} – {{ rule.end_time }}<span v-if="isOvernight(rule)" class="ms-1 text-slate-500">{{ t('happyHour.overnightHint') }}</span></p>
      <p class="text-[11px] text-slate-500">
        {{ rule.days && rule.days.length ? dayLabels(rule.days) : t('ownerPromotions.daysHint') }}
      </p>
      <p class="text-[11px] text-slate-500">
        {{ rule.category_ids && rule.category_ids.length ? t('happyHour.scope_some', { n: rule.category_ids.length }) : t('happyHour.allCategories') }}
      </p>
    </div>
    <div class="flex shrink-0 gap-2">
      <button
        class="ui-btn-outline ui-press min-h-[44px] px-3 py-2 text-xs font-medium"
        :aria-label="t('happyHour.editAriaLabel', { name: rule.name })"
        @click="emit('edit', rule)"
      >{{ t('common.edit') }}</button>
      <button
        class="ui-press min-h-[44px] rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-400 hover:border-red-500/50 hover:bg-red-500/15 hover:text-red-300 transition-colors disabled:opacity-50"
        :aria-label="t('happyHour.deleteAriaLabel', { name: rule.name })"
        :disabled="deleting"
        @click="emit('delete', rule)"
      >{{ t('common.delete') }}</button>
    </div>
  </article>
</template>

<script setup>
// A single happy-hour rule card from OwnerPromotions.vue's Happy Hours list,
// extracted as a standalone presentational child (RISK FE-2). Display only: it
// renders one rule (name, active status, percent off, time window, days, scope)
// and forwards its two actions (edit / delete, each with the rule) to the parent
// via emits. The parent keeps the rules list, the API mutations (openEditHH /
// deleteHHRule) and the in-flight hhDeletingId guard (passed back as `deleting`).
// `isOvernight` (the overnight-window predicate) and `dayLabels` (the day-label
// formatter) are passed down as function props so they stay single-sourced in
// the parent; `index` drives the same staggered reveal the inline v-for used.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The happy-hour rule to render. */
  rule: { type: Object, required: true },
  /** Row index within the list — drives the staggered --ui-delay reveal. */
  index: { type: Number, default: 0 },
  /** Predicate (rule) => bool: whether the window crosses midnight. */
  isOvernight: { type: Function, required: true },
  /** Formatter (days[]) => string for the active-days line. */
  dayLabels: { type: Function, required: true },
  /** True while this rule's delete request is in flight. */
  deleting: { type: Boolean, default: false },
});

const emit = defineEmits(['edit', 'delete']);
</script>
