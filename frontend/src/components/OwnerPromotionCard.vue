<template>
  <article
    :aria-labelledby="`promo-name-${promo.id}`"
    class="ui-panel ui-surface-lift ui-reveal p-4 flex items-start justify-between gap-4"
    :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
  >
    <div class="flex-1 min-w-0 space-y-1.5">
      <!-- Name + status badge -->
      <div class="flex items-center gap-2 flex-wrap">
        <span :id="`promo-name-${promo.id}`" class="text-sm font-semibold text-white leading-snug">{{ promo.name }}</span>
        <span
          class="ui-status-pill shrink-0 inline-flex items-center gap-1"
          :class="promo.is_active
            ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
            : 'border-slate-600/60 bg-slate-700/30 text-slate-400'"
        >
          <span
            class="h-1.5 w-1.5 rounded-full shrink-0"
            :class="promo.is_active ? 'bg-emerald-400' : 'bg-slate-500'"
            aria-hidden="true"
          />
          {{ promo.is_active ? t('ownerPromotions.activeNow') : t('ownerPromotions.inactive') }}
        </span>
      </div>
      <!-- Discount label -->
      <p class="text-xs font-medium text-slate-300">{{ promoLabel(promo) }}</p>
      <!-- Promo code badge -->
      <p v-if="promo.code" class="inline-flex items-center gap-1 rounded-md border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-mono font-semibold text-indigo-300">
        <span class="opacity-60 font-sans font-normal not-italic">{{ t('ownerPromotions.codeLabel') }}:</span>{{ promo.code }}
      </p>
      <!-- Description -->
      <p v-if="promo.description" class="text-xs text-slate-500 truncate" :title="promo.description">{{ promo.description }}</p>
      <!-- Metadata chips -->
      <div class="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-slate-500 tabular-nums pt-0.5">
        <span v-if="promo.min_order_amount && Number(promo.min_order_amount) > 0">
          {{ t('ownerPromotions.minOrderShort', { amount: promo.min_order_amount }) }}
        </span>
        <span v-if="promo.days && promo.days.length">{{ promo.days.join(', ') }}</span>
        <span v-if="promo.time_start && promo.time_end">{{ promo.time_start }}–{{ promo.time_end }}</span>
        <span v-if="promo.active_from || promo.active_until">
          {{ promo.active_from || '∞' }} → {{ promo.active_until || '∞' }}
        </span>
        <span>{{ t('ownerPromotions.useCount_other', { count: promo.use_count }) }}</span>
      </div>
    </div>
    <!-- Actions -->
    <div class="flex shrink-0 items-start gap-2">
      <!-- Active toggle -->
      <button
        type="button"
        role="switch"
        :aria-checked="promo.is_active"
        :aria-label="t('ownerPromotions.toggleActiveAriaLabel', { name: promo.name })"
        :disabled="toggling"
        class="ui-press mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60 disabled:opacity-50"
        :class="promo.is_active
          ? 'border-emerald-500/60 bg-emerald-500/80'
          : 'border-slate-600/60 bg-slate-700/50'"
        @click="emit('toggle', promo)"
      >
        <span
          class="pointer-events-none mx-0.5 h-3.5 w-3.5 rounded-full shadow transition-transform"
          :class="promo.is_active ? 'translate-x-4 bg-white' : 'translate-x-0 bg-slate-400'"
        />
      </button>
      <!-- Duplicate -->
      <button
        type="button"
        class="ui-press min-h-[44px] rounded-lg border border-slate-600/50 bg-slate-700/30 px-3 py-2 text-xs font-medium text-slate-300 hover:border-slate-500/60 hover:bg-slate-700/50 hover:text-white transition-colors"
        :aria-label="t('ownerPromotions.clonePromoAriaLabel', { name: promo.name })"
        @click="emit('clone', promo)"
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5">
          <rect x="7" y="7" width="10" height="10" rx="2" />
          <path d="M3 13V5a2 2 0 0 1 2-2h8" />
        </svg>
      </button>
      <!-- Edit -->
      <button
        class="ui-btn-outline ui-press min-h-[44px] px-3 py-2 text-xs font-medium"
        :aria-label="t('ownerPromotions.editAriaLabel', { name: promo.name })"
        @click="emit('edit', promo)"
      >{{ t('common.edit') }}</button>
      <!-- Delete -->
      <button
        class="ui-press min-h-[44px] rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-400 hover:border-red-500/50 hover:bg-red-500/15 hover:text-red-300 transition-colors disabled:opacity-50"
        :aria-label="t('ownerPromotions.deleteAriaLabel', { name: promo.name })"
        :disabled="deleting"
        @click="emit('delete', promo)"
      >{{ t('common.delete') }}</button>
    </div>
  </article>
</template>

<script setup>
// A single promotion card from OwnerPromotions.vue's list, extracted as a
// standalone presentational child (RISK FE-2). Display only: it renders one
// promotion (name, status, discount label, code, description, metadata chips)
// and four action buttons that forward intent to the parent via emits
// (toggle / clone / edit / delete, each with the promo). The parent keeps the
// promotions list, the API mutations, and the in-flight togglingId/deletingId
// guards (passed back in as the `toggling`/`deleting` booleans). `promoLabel`
// (the discount-label formatter) is passed down as a function prop so it stays
// single-sourced in the parent; `index` drives the same staggered reveal delay
// the inline v-for used. No API calls or store access here.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The promotion to render. */
  promo: { type: Object, required: true },
  /** Row index within the list — drives the staggered --ui-delay reveal. */
  index: { type: Number, default: 0 },
  /** Discount-label formatter (promo) => string, owned by the parent. */
  promoLabel: { type: Function, required: true },
  /** True while this promo's active-toggle request is in flight. */
  toggling: { type: Boolean, default: false },
  /** True while this promo's delete request is in flight. */
  deleting: { type: Boolean, default: false },
});

const emit = defineEmits(['toggle', 'clone', 'edit', 'delete']);
</script>
