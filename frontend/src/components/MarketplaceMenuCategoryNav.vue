<template>
  <!-- Sticky horizontal category navigation -->
  <nav
    class="sticky top-0 z-20 -mx-4 mt-1 border-b border-slate-800/50 bg-slate-950/95 backdrop-blur-md"
    :class="categories.length > 1 ? 'mb-2' : 'mb-1'"
    aria-label="Menu categories"
    style="scrollbar-width: none; -webkit-overflow-scrolling: touch;"
  >
    <div v-if="categories.length > 1" class="flex gap-1.5 overflow-x-auto px-4 py-2" style="scrollbar-width: none;">
      <button
        v-for="cat in categories"
        :key="cat.id"
        type="button"
        class="shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-[11px] font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
        :class="activeCategoryId === cat.id
          ? 'bg-[var(--color-secondary)] text-slate-950 shadow-sm shadow-[var(--color-secondary)]/30'
          : 'border border-slate-700/70 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
        @click="emit('select-category', cat.id)"
      >
        {{ cat.name }}
      </button>
    </div>
    <!-- Search strip -->
    <div class="border-t border-slate-800/40 px-4 py-2">
      <div class="relative flex items-center">
        <span class="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden="true">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" class="h-3.5 w-3.5"><circle cx="6.5" cy="6.5" r="4"/><path d="M10.5 10.5 14 14"/></svg>
        </span>
        <input
          :value="searchQuery"
          type="search"
          :placeholder="t('mktMenu.searchPlaceholder')"
          :aria-label="t('mktMenu.search')"
          class="ui-input ps-8 pe-8"
          @input="emit('search-input', $event.target.value)"
        />
        <button
          v-if="isSearchActive"
          type="button"
          class="absolute end-2.5 top-1/2 -translate-y-1/2 rounded-full p-0.5 text-slate-500 transition-colors hover:text-slate-300"
          :aria-label="t('mktMenu.searchClear')"
          @click="emit('clear-search')"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3.5 w-3.5" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
        </button>
      </div>
    </div>
    <!-- Allergen "Free from" strip — only shown when at least one dish has allergen data -->
    <div
      v-if="availableAllergens.length"
      role="group"
      :aria-label="t('mktMenu.allergenFilter')"
      class="flex items-center gap-2 overflow-x-auto border-t border-slate-800/40 px-4 py-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      <span class="shrink-0 text-[10px] font-semibold uppercase tracking-widest text-slate-500">{{ t('mktMenu.freeFrom') }}</span>
      <button
        v-for="allergen in availableAllergens"
        :key="allergen"
        type="button"
        :aria-pressed="selectedAllergens.includes(allergen)"
        class="ui-touch-target shrink-0 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
        :class="selectedAllergens.includes(allergen)
          ? 'border-amber-400/70 bg-amber-500/20 text-amber-200'
          : 'border-slate-700 bg-slate-900/60 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
        @click="emit('toggle-allergen', allergen)"
      >{{ t(`mktMenu.allergen_${allergen}`) }}</button>
      <!-- Hidden items counter shown when filter is active -->
      <Transition name="ui-fade">
        <span
          v-if="allergenHiddenCount > 0"
          class="ms-auto shrink-0 whitespace-nowrap rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300"
        >{{ t('mktMenu.allergenHidden', { n: allergenHiddenCount }) }}</span>
      </Transition>
    </div>
  </nav>
</template>

<script setup>
// Sticky category-tabs / search / allergen-filter navigation strip of
// MarketplaceMenuPage.vue (customer menu-browsing page), extracted as a
// standalone presentational component (RISK FE-2). This is DISPLAY +
// FILTER-UI ONLY — no cart, add-to-cart, option-selection, or money logic
// lives here. All state (active category, search text, allergen selection)
// is owned by the parent and passed down as props; every user interaction
// (tap a category, type/clear the search box, toggle an allergen chip) is
// forwarded up via emits for the parent's existing handlers to apply, so
// behavior is byte-for-byte identical to the original inline template.
// The search input deliberately uses plain :value/@input (not v-model) and
// forwards the RAW typed value — the parent owns the ref and assigns it
// directly, mirroring the proven CartPromoCode.vue extraction.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Categories that currently have dishes, in display order: [{ id, name }]. */
  categories: { type: Array, default: () => [] },
  /** id of the category highlighted as active (sticky-nav scroll-spy), or null. */
  activeCategoryId: { type: [Number, String], default: null },
  /** Current search box value (owned by the parent). */
  searchQuery: { type: String, default: '' },
  /** Whether the search query is non-blank (parent-derived; shows the clear button). */
  isSearchActive: { type: Boolean, default: false },
  /** Allergens present on at least one dish on this menu. */
  availableAllergens: { type: Array, default: () => [] },
  /** Allergens the customer has excluded ("free from"). */
  selectedAllergens: { type: Array, default: () => [] },
  /** Count of dishes hidden by the active allergen filter. */
  allergenHiddenCount: { type: Number, default: 0 },
});

const emit = defineEmits(['select-category', 'search-input', 'clear-search', 'toggle-allergen']);
</script>
