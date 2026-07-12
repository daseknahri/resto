<template>

  <!-- Loading -->
  <div v-if="loading" class="ui-panel p-4 space-y-2">
    <div v-for="i in 2" :key="i" class="h-24 animate-pulse rounded-xl bg-slate-800/50" />
  </div>

  <!-- No completed orders at all -->
  <div v-else-if="!completedOrders.length" class="ui-empty-state text-center p-8 space-y-2">
    <AppIcon name="star" class="mx-auto h-8 w-8 text-slate-600" aria-hidden="true" />
    <p class="text-sm font-semibold text-slate-300">{{ t('customerAccount.reviewsEmpty') }}</p>
    <p class="text-xs text-slate-500">{{ t('customerAccount.reviewsEmptyHint') }}</p>
  </div>

  <template v-else>

    <!-- Average score card -->
    <div v-if="submittedReviews.length" class="relative overflow-hidden rounded-3xl border border-amber-500/20 bg-gradient-to-br from-amber-500/8 via-slate-900/95 to-slate-950 p-4">
      <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(245,158,11,0.07),transparent_65%)]" />
      <div class="relative flex items-center gap-4">
        <div class="text-center">
          <p class="text-4xl font-black tabular-nums leading-none text-amber-400">{{ reviewsAvgScore.toFixed(1) }}</p>
          <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.reviewsOutOf5') }}</p>
        </div>
        <div class="flex-1 space-y-1">
          <div class="flex gap-0.5">
            <span
              v-for="s in 5"
              :key="s"
              class="text-xl leading-none"
              :class="s <= Math.round(reviewsAvgScore) ? 'text-amber-400' : 'text-slate-700'"
            >★</span>
          </div>
          <p class="text-[11px] text-slate-400">
            {{ t('customerAccount.reviewsSubmittedCount', { count: submittedReviews.length }) }}
            <span v-if="pendingReviews.length" class="ms-1.5 text-amber-400">{{ t('customerAccount.reviewsPending', { count: pendingReviews.length }) }}</span>
          </p>
        </div>
      </div>
    </div>

    <!-- ── Pending reviews ── -->
    <div v-if="pendingReviews.length" class="ui-panel overflow-hidden p-0">
      <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
        <div>
          <p class="ui-kicker">{{ t('customerAccount.reviewsWriteSection') }}</p>
          <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.reviewsWriteSubtitle') }}</p>
        </div>
        <span class="rounded-full border border-amber-500/40 bg-amber-500/12 px-2 py-0.5 text-[11px] font-semibold tabular-nums text-amber-400">{{ pendingReviews.length }}</span>
      </div>
      <div class="p-4 space-y-4">
        <div
          v-for="(order, idx) in pendingReviews"
          :key="order.order_number"
          class="ui-reveal rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3.5 space-y-3"
          :style="{ '--ui-delay': `${Math.min(idx, 9) * 40}ms` }"
        >
          <!-- Order info -->
          <div class="flex items-center gap-2 text-[11px]">
            <RouterLink
              :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
              class="font-bold text-[var(--color-secondary)] hover:opacity-80"
            >#{{ order.order_number }}</RouterLink>
            <span class="text-slate-600">·</span>
            <span class="text-slate-500">{{ formatDate(order.created_at) }}</span>
            <span v-if="order.total" class="ms-auto tabular-nums text-slate-400">{{ formatPrice(order.total) }}</span>
          </div>

          <!-- Interactive star selector -->
          <div class="space-y-1">
            <p class="text-[11px] text-slate-400">{{ t('customerAccount.reviewsYourRating') }}</p>
            <div class="flex items-center gap-0.5">
              <button
                v-for="s in 5"
                :key="s"
                type="button"
                class="select-none text-[26px] leading-none transition-all active:scale-90"
                :class="s <= (reviewHover[order.order_number] || getDraft(order.order_number).score)
                  ? 'text-amber-400'
                  : 'text-slate-700 hover:text-slate-500'"
                :aria-label="t('common.rateNStars', { n: s })"
                :aria-pressed="s <= getDraft(order.order_number).score"
                @mouseenter="emit('hover', order.order_number, s)"
                @mouseleave="emit('hover', order.order_number, 0)"
                @click="emit('draft-score', order.order_number, s)"
              >★</button>
              <span
                v-if="getDraft(order.order_number).score || reviewHover[order.order_number]"
                class="ms-2.5 text-xs font-semibold"
                :class="getDraft(order.order_number).score ? 'text-amber-400' : 'text-slate-500'"
                aria-live="polite"
                role="status"
              >{{ reviewScoreLabels[reviewHover[order.order_number] || getDraft(order.order_number).score] }}</span>
            </div>
          </div>

          <!-- Optional comment (shown after a score is set) -->
          <Transition name="ui-expand">
            <div v-if="getDraft(order.order_number).score" class="space-y-1.5">
              <p class="text-[11px] text-slate-400">{{ t('customerAccount.reviewsComment') }} <span class="text-slate-600">{{ t('customerAccount.reviewsCommentOptional') }}</span></p>
              <textarea
                :value="getDraft(order.order_number).comment"
                rows="2"
                maxlength="500"
                class="ui-textarea w-full resize-none text-xs leading-relaxed"
                :aria-label="t('customerAccount.reviewsComment')"
                :placeholder="t('customerAccount.reviewsCommentPlaceholder')"
                @input="emit('draft-comment', order.order_number, $event.target.value)"
              />
              <p class="mt-1 text-end text-xs tabular-nums" :class="(getDraft(order.order_number).comment || '').length >= 480 ? 'text-amber-400' : 'text-slate-600'" aria-live="polite">{{ (getDraft(order.order_number).comment || '').length }}/500</p>
            </div>
          </Transition>

          <!-- Submit button -->
          <button
            class="ui-btn-primary w-full justify-center py-2 text-xs"
            :disabled="!getDraft(order.order_number).score || submittingReview.has(order.order_number)"
            @click="emit('submit', order)"
          >
            <AppIcon
              v-if="submittingReview.has(order.order_number)"
              name="refresh"
              class="h-3.5 w-3.5 animate-spin"
            />
            {{ submittingReview.has(order.order_number) ? t('customerAccount.reviewsSubmitting') : t('customerAccount.reviewsSubmit') }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── Submitted reviews ── -->
    <div v-if="submittedReviews.length" class="ui-panel overflow-hidden p-0">
      <div class="border-b border-slate-800/70 px-4 py-3">
        <p class="ui-kicker">{{ t('customerAccount.reviewsSubmittedSection') }}</p>
      </div>
      <div class="p-4 space-y-3">
        <div
          v-for="order in submittedReviews"
          :key="order.order_number"
          class="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3.5 space-y-2"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="space-y-0.5">
              <RouterLink
                :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
                class="text-xs font-bold text-[var(--color-secondary)] hover:opacity-80"
              >#{{ order.order_number }}</RouterLink>
              <p class="text-[10px] text-slate-500">{{ formatDate(order.created_at) }}</p>
            </div>
            <div class="flex flex-col items-end gap-0.5">
              <div class="flex gap-0.5">
                <span
                  v-for="s in 5"
                  :key="s"
                  class="text-base leading-none"
                  :class="s <= order.rating_score ? 'text-amber-400' : 'text-slate-700'"
                >★</span>
              </div>
              <p class="text-[10px] text-slate-500">{{ order.rating_score }}/5</p>
            </div>
          </div>
          <p v-if="order.rating?.comment" class="rounded-xl border border-slate-700/50 bg-slate-950/40 px-3 py-2 text-xs italic leading-relaxed text-slate-300">
            "{{ order.rating.comment }}"
          </p>
        </div>
      </div>
    </div>

  </template>
</template>

<script setup>
// Reviews tab of CustomerAccount.vue, extracted as a standalone child
// component (RISK FE-2). Fetch/state ownership stays in the parent
// (CustomerAccount.vue) — the underlying order list, loading flag, review
// drafts and in-flight submissions are all computed/owned there because they
// are also used elsewhere on the page (stats tiles, tab-nav dot, overview
// tile). This component is purely presentational: it renders whatever data
// it's given and asks the parent to apply mutations via emits (`hover`,
// `draft-score`, `draft-comment`, `submit`).
import { RouterLink } from 'vue-router';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t, formatPrice, currentLocale } = useI18n();

const props = defineProps({
  /** True while the parent is fetching the customer's orders. */
  loading: { type: Boolean, default: false },
  /** All of the customer's completed orders (across restaurants). */
  completedOrders: { type: Array, default: () => [] },
  /** Completed orders that have not been rated yet. */
  pendingReviews: { type: Array, default: () => [] },
  /** Completed orders that already have a rating. */
  submittedReviews: { type: Array, default: () => [] },
  /** Average of submittedReviews' rating_score. */
  reviewsAvgScore: { type: Number, default: 0 },
  /** Reactive map of orderNumber -> hovered star count (0-5), owned by the parent. */
  reviewHover: { type: Object, default: () => ({}) },
  /** Reactive map of orderNumber -> { score, comment } draft, owned by the parent. */
  reviewDrafts: { type: Object, default: () => ({}) },
  /** Set of orderNumbers currently being submitted, owned by the parent. */
  submittingReview: { type: Object, default: () => new Set() },
  /** Locale-aware score labels, index 0-5 (index 0 unused). */
  reviewScoreLabels: { type: Array, default: () => ['', '', '', '', '', ''] },
});

const emit = defineEmits(['hover', 'draft-score', 'draft-comment', 'submit']);

const getDraft = (num) => props.reviewDrafts[num] ?? { score: 0, comment: '' };

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(iso));
  } catch { return iso; }
};
</script>
