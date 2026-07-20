<template>
  <!-- Loyalty points teaser — shown when signed in + loyalty enabled -->
  <div
    class="ui-reveal mx-4 mb-2 flex items-center gap-2.5 rounded-xl border border-violet-500/25 bg-violet-500/8 px-4 py-2"
    :style="{ '--ui-delay': '70ms' }"
    role="note"
  >
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0 text-violet-400" aria-hidden="true">
      <path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.75.75 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z" />
    </svg>
    <div class="min-w-0 flex-1">
      <p class="text-[12px] font-semibold leading-tight text-violet-200">
        {{ points > 0 ? t('mktMenu.loyaltyTeaserPts', { points }) : t('mktMenu.loyaltyTeaserEarn') }}
      </p>
      <p v-if="earnProjection > 0" class="text-[10px] leading-tight text-violet-400/80">{{ t('mktMenu.loyaltyEarnProjection', { points: earnProjection }) }}</p>
      <p v-else-if="available" class="text-[10px] leading-tight text-violet-400/80">{{ t('mktMenu.loyaltyTeaserRedeem') }}</p>
    </div>
    <span
      v-if="points > 0"
      class="shrink-0 rounded-full border border-violet-500/20 bg-violet-500/15 px-2 py-0.5 text-[11px] font-bold tabular-nums text-violet-300"
    >{{ points }}</span>
  </div>
</template>

<script setup>
// Loyalty-points teaser of MarketplaceMenuPage.vue (customer menu-browsing page),
// extracted as a standalone presentational child (RISK FE-2). Display only: it
// shows the customer's current loyalty points (or an earn prompt), an optional
// earn-projection / redeem line, and a points badge. The
// `loyaltyConfig?.enabled && customerStore.isAuthenticated` render gate stays in
// the parent (which conditionally renders this component), and the loyalty state
// (points, projection, availability) is passed down as props — this component
// makes no API calls, has no emits, and mutates nothing (the actual redemption
// checkbox lives elsewhere in the parent's checkout drawer, untouched).
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Current loyalty points balance for this customer × tenant. */
  points: { type: Number, default: 0 },
  /** Points the current basket would earn (shown when > 0), else 0. */
  earnProjection: { type: Number, default: 0 },
  /** Whether points can be redeemed now (drives the fallback redeem hint). */
  available: { type: Boolean, default: false },
});
</script>
