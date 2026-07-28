<template>
  <!-- Browse-only notice -->
  <div class="ui-section-band border-sky-500/40 bg-sky-500/10 px-4 py-3 text-sky-100 space-y-0.5">
    <p class="text-sm font-semibold">{{ t('cartPage.orderingDisabled') }}</p>
    <p class="text-xs text-sky-200/75">{{ t('cartPage.browseOnlyBody') }}</p>
  </div>
</template>

<script setup>
// "Browse-only plan" notice of Cart.vue, extracted as a standalone presentational
// child (RISK FE-2). Pure display — the `isBrowseOnlyPlan` condition (the head of
// the browse/empty/main v-if chain) stays on the parent's
// <CartBrowseOnlyBanner v-if="isBrowseOnlyPlan" />.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();
</script>
