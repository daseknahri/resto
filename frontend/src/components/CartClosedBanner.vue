<template>
  <!-- Restaurant closed notice -->
  <div
    class="ui-section-band border-amber-500/40 bg-amber-500/10 px-4 py-3 text-amber-100 space-y-0.5"
    role="status"
  >
    <p class="text-sm font-semibold">{{ t('cartPage.restaurantClosed') }}</p>
    <p class="text-xs text-amber-200/75">{{ t('cartPage.restaurantClosedBody') }}</p>
  </div>
</template>

<script setup>
// "Restaurant closed" notice of Cart.vue, extracted as a standalone presentational
// child (RISK FE-2). Pure display — the visibility condition (`!isRestaurantOpen
// && !isBrowseOnlyPlan`) stays on the parent's <CartClosedBanner v-if="…" />.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();
</script>
