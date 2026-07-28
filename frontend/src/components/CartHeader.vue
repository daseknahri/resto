<template>
  <!-- ── Header ──────────────────────────────────────────────────────────── -->
  <header class="ui-hero-ribbon ui-reveal px-4 py-4 md:px-5 md:py-5">
    <div class="flex items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div>
          <p class="ui-kicker">{{ t('cartPage.kicker') }}</p>
          <h1 class="ui-display text-2xl font-bold tracking-tight text-white md:text-3xl leading-tight">
            {{ t('common.cart') }}
          </h1>
        </div>
        <div v-if="hasItems" class="flex items-center gap-1.5">
          <span class="ui-chip">{{ countLabel }}</span>
          <span class="ui-chip">{{ planLabel }}</span>
          <span v-if="tableLabel" class="ui-chip">{{ t('cartPage.table', { table: tableLabel }) }}</span>
        </div>
      </div>
      <button
        v-if="hasItems"
        class="shrink-0 ui-btn-outline px-2.5 py-1.5 text-xs text-red-200 hover:border-red-400/50"
        @click="emit('clear')"
      >
        <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
        {{ t('common.clear') }}
      </button>
    </div>
  </header>
</template>

<script setup>
// Cart page header, extracted as a standalone presentational child (RISK FE-2).
// Display only: the kicker + title, the item-count / plan / table chips (shown
// when the cart has items), and the clear-cart button. It owns no cart state and
// mutates nothing — the count/plan/table labels are passed in as props (derived
// in the parent from the cart store), and the clear button forwards intent via
// the `clear` emit so the parent keeps ownership of `clearCart`. Nothing here
// touches pricing, payment or checkout.
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Whether the cart has any items (shows the chips + clear button). */
  hasItems: { type: Boolean, default: false },
  /** Pre-formatted item-count label (itemCountLabel(cart.count)). */
  countLabel: { type: String, default: '' },
  /** The tenant plan label. */
  planLabel: { type: String, default: '' },
  /** The selected table label, or '' when none. */
  tableLabel: { type: String, default: '' },
});

const emit = defineEmits(['clear']);
</script>
