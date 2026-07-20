<template>
  <!-- Empty state -->
  <div class="ui-empty-state ui-reveal text-center space-y-2">
    <p class="text-base font-semibold text-slate-100">{{ t('cartPage.cartEmpty') }}</p>
    <p class="text-sm text-slate-400">{{ t('cartPage.cartEmptyBody') }}</p>
    <RouterLink :to="{ name: 'menu' }" class="ui-btn-primary mt-4 inline-flex items-center gap-1.5 px-6 py-2.5 text-sm font-semibold tracking-wide">
      <AppIcon name="menu" class="h-4 w-4" />{{ t('cartPage.browseMenu') }}
    </RouterLink>
  </div>
</template>

<script setup>
// Empty-cart state of Cart.vue, extracted as a standalone presentational child
// (RISK FE-2). Pure display — the empty message + a link back to the menu. The
// `v-else-if="!cart.items.length"` chain position stays on the parent's
// <CartEmptyState v-else-if="…" />.
import { RouterLink } from 'vue-router';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();
</script>
