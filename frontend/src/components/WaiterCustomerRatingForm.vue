<template>
  <div>
    <p class="ui-kicker">{{ t('ownerOrders.customerRatingTitle') }}</p>
    <p class="mt-0.5 text-xs text-slate-400">
      {{ order.customer_name || order.table_label || ('#' + order.order_number) }}
    </p>
    <p class="mt-1 text-[11px] text-slate-500">{{ t('ownerOrders.customerRatingHint') }}</p>
  </div>
  <div class="flex items-center gap-1.5" role="group" :aria-label="t('ownerOrders.customerRatingTitle')">
    <button
      v-for="n in 5" :key="n" type="button"
      class="ui-press text-3xl leading-none transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60"
      :class="n <= score ? 'text-amber-400' : 'text-slate-600'"
      :aria-label="t('common.rateNStars', { n })"
      :aria-pressed="n <= score"
      @click="score = n"
    >★</button>
  </div>
  <input
    v-model="note" type="text" maxlength="200"
    class="ui-input"
    :aria-label="t('ownerOrders.customerRatingNote')"
    :placeholder="t('ownerOrders.customerRatingNote')"
  />
  <div class="flex items-center justify-end gap-2 pt-1">
    <button class="ui-press ui-touch-target px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500/60" @click="emit('close')">
      {{ t('common.cancel') }}
    </button>
    <button
      class="ui-btn-primary ui-press inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
      :disabled="!score || busy"
      :aria-busy="busy"
      @click="emit('submit')"
    >
      <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
      {{ busy ? t('common.loading') : t('ownerOrders.customerRatingSubmit') }}
    </button>
  </div>
</template>

<script setup>
// The inner form body of WaiterPage.vue's customer trust-rating modal (RISK FE-2).
// Deliberately a FRAGMENT child (no wrapper root) so its four blocks stay direct
// children of the parent's role="dialog" panel — the panel's `space-y-3` rhythm and
// the parent-owned focus trap (which queries that dialog's DOM via `ratingDialogRef`)
// are therefore untouched. The parent (WaiterPage.vue) keeps the whole modal shell
// (Teleport / Transition / backdrop / dialog + focus trap), the submit handler
// (`submitCustomerRating` → waiter.rateCustomer) and the score/note refs; here the
// score + note are two-way models, and cancel/submit are emits.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The order being rated — supplies the header identity line (ratingOrder). */
  order: { type: Object, required: true },
  /** Whether a submit is in flight (submittingCustRating). */
  busy: { type: Boolean, default: false },
});

/** The star score (custRatingScore), two-way. */
const score = defineModel('score', { type: Number, default: 0 });
/** The free-text note (custRatingNote), two-way. */
const note = defineModel('note', { type: String, default: '' });

const emit = defineEmits(['close', 'submit']);
</script>
