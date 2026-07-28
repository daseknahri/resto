<template>
  <!-- Customer reviews — horizontal scroll, only shown when restaurant has review comments -->
  <div
    class="ui-reveal mb-2 space-y-2"
    :style="{ '--ui-delay': '90ms' }"
  >
    <p class="ui-kicker px-4">{{ t('mktMenu.reviewsTitle') }}</p>
    <div class="flex gap-2.5 overflow-x-auto px-4 pb-0.5 snap-x">
      <div
        v-for="(review, idx) in reviews"
        :key="idx"
        class="w-56 shrink-0 snap-start rounded-xl border border-slate-800/70 bg-slate-900/50 px-3 py-2.5 space-y-1"
      >
        <div class="flex items-center gap-0.5 text-amber-400 text-[11px]">
          <span :aria-label="`${review.score} stars`">{{ '★'.repeat(review.score) }}<span class="opacity-25">{{ '★'.repeat(5 - review.score) }}</span></span>
        </div>
        <p class="line-clamp-3 text-[11px] leading-relaxed text-slate-300">{{ review.comment }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
// Customer-reviews horizontal-scroll rail of MarketplaceMenuPage.vue (customer
// menu-browsing page), extracted as a standalone presentational component
// (RISK FE-2). This is DISPLAY ONLY — no cart, add-to-cart, option-selection,
// or money logic lives here or is shared with it; it just renders the list of
// reviews it's given. The parent still owns the `restaurant.recent_reviews?.length`
// visibility guard (see MarketplaceMenuPage.vue), so this component is only
// mounted when there's at least one review, matching the original inline
// template's behavior exactly.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Recent reviews to display: [{ score: number (1-5), comment: string }]. */
  reviews: { type: Array, default: () => [] },
});
</script>
