<template>
  <!-- Cart items -->
  <div class="space-y-2">
    <article
      v-for="item in cart"
      :key="item.slug"
      class="relative flex items-center gap-3 overflow-hidden rounded-xl border border-slate-800/60 bg-slate-900/60 py-2.5 ps-3.5 pe-2.5"
    >
      <!-- left accent bar -->
      <div
        class="pointer-events-none absolute inset-y-0 start-0 w-[3px] rounded-s-xl"
        style="background: linear-gradient(to bottom, rgba(245,158,11,0.55), rgba(245,158,11,0.10))"
      />
      <!-- info -->
      <div class="flex-1 min-w-0 space-y-0.5">
        <p class="truncate text-sm font-semibold leading-snug" :class="unavailableSlugs.has(item.slug) ? 'text-slate-400 line-through' : 'text-slate-100'" :title="item.name">{{ item.name }}</p>
        <p v-if="unavailableSlugs.has(item.slug)" class="text-[10px] font-semibold text-red-400">{{ t('mktMenu.cartItemUnavailable') }}</p>
        <p v-if="item.options?.length" class="truncate text-[11px] text-slate-500 leading-snug">{{ item.options.map(o => o.name).join(', ') }}</p>
        <p class="text-xs tabular-nums">
          <span class="font-semibold text-[var(--color-secondary)]">{{ fmtPrice((item.unitPrice ?? item.price) * item.qty) }}</span>
          <span class="text-slate-500"> · {{ fmtPrice(item.unitPrice ?? item.price) }} ea.</span>
        </p>
      </div>
      <!-- stepper pill -->
      <div class="inline-flex shrink-0 items-center gap-0.5 rounded-full border border-slate-700/60 bg-slate-900/70 px-0.5">
        <button
          class="ui-press flex h-10 w-10 items-center justify-center rounded-full text-slate-400 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
          :aria-label="`${t('dishPage.decreaseQuantity')} ${item.name}`"
          @click="emit('decrement', item.slug)"
        >
          <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M2 6h8"/></svg>
        </button>
        <span class="min-w-[1.25rem] text-center text-sm font-bold tabular-nums text-white" aria-live="polite" aria-atomic="true">{{ item.qty }}</span>
        <button
          class="ui-press flex h-10 w-10 items-center justify-center rounded-full text-slate-400 transition hover:text-slate-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-secondary)]/60"
          :aria-label="`${t('dishPage.increaseQuantity')} ${item.name}`"
          @click="emit('increment', item.slug)"
        >
          <svg viewBox="0 0 12 12" class="h-3 w-3 shrink-0" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" fill="none" aria-hidden="true"><path d="M6 1v10M1 6h10"/></svg>
        </button>
      </div>
    </article>
  </div>
</template>

<script setup>
// The cart line-item list of MarketplaceMenuPage.vue's checkout drawer, extracted as
// a PRESENTATIONAL child (RISK FE-2) — the first sub-part of the checkout-drawer
// split. Display + qty stepper only: it renders each cart line (name, chosen
// options, line + unit price, an unavailable flag) with a −/＋ stepper, and forwards
// the taps as `decrement` / `increment` emits carrying the item slug. It owns NO
// cart or payment logic: the parent keeps the `cart` array and the mutation handlers
// (removeFromCart / addToCartBySlug) and all of placeOrder. `unavailableSlugs` +
// `fmtPrice` are passed in.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The cart line items ({ slug, name, qty, price, unitPrice, options }). */
  cart: { type: Array, default: () => [] },
  /** Set of slugs no longer available (struck through + flagged). */
  unavailableSlugs: { type: [Set, Object], default: () => new Set() },
  /** Price formatter (fmtPrice). */
  fmtPrice: { type: Function, required: true },
});

const emit = defineEmits(['decrement', 'increment']);
</script>
