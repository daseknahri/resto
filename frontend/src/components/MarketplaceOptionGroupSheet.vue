<template>
  <div
    ref="rootRef"
    role="dialog"
    aria-modal="true"
    :aria-label="dish.name"
    class="fixed inset-0 z-50 flex flex-col"
    @keydown.esc="emit('close')"
  >
    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm"
      aria-hidden="true"
      @click="emit('close')"
    />
    <!-- Sheet (slides up from bottom, max ~88 vh) -->
    <div
      class="relative mt-auto mx-auto w-full max-w-md overflow-hidden rounded-t-3xl border-t border-slate-800/60 bg-[#0b0d13] shadow-2xl flex flex-col"
      style="max-height: 88vh"
    >
      <!-- Handle bar -->
      <div class="flex justify-center pt-3 pb-1 shrink-0" aria-hidden="true">
        <div class="h-1 w-10 rounded-full bg-slate-700" />
      </div>
      <!-- Dish header -->
      <div class="flex items-start gap-3 px-5 py-3.5 border-b border-slate-800/50 shrink-0">
        <!-- Larger image when available -->
        <div
          v-if="dish.image_url"
          class="h-16 w-16 shrink-0 rounded-xl overflow-hidden bg-slate-800"
        >
          <img :src="dish.image_url" :alt="dish.name" loading="lazy" class="h-full w-full object-cover" />
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-base font-bold text-white leading-snug">{{ dish.name }}</p>
          <!-- Base price + optional flash-sale strikethrough -->
          <div class="mt-0.5 flex items-baseline gap-1.5">
            <span v-if="flashSalePct" class="text-[11px] tabular-nums text-amber-200/50 line-through">{{ fmtPrice(dish.price) }}</span>
            <span
              class="text-sm font-bold tabular-nums"
              :class="flashSalePct ? 'text-amber-400' : 'text-[var(--color-secondary)]'"
            >{{ fmtPrice(flashSalePct ? dishSalePrice(dish.price) : dish.price) }}</span>
          </div>
          <!-- Dietary tags -->
          <div v-if="dish.tags?.length" class="mt-1.5 flex flex-wrap gap-1">
            <span
              v-for="tag in dish.tags"
              :key="tag"
              class="rounded-full border px-1.5 py-0.5 text-[10px] font-medium"
              :class="tagBadgeClass(tag)"
            >{{ tag }}</span>
          </div>
        </div>
        <button
          type="button"
          class="ui-press flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-700/60 text-slate-400 transition hover:border-slate-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40"
          :aria-label="t('common.close')"
          @click="emit('close')"
        >
          <svg viewBox="0 0 16 16" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>
        </button>
      </div>

      <!-- Scrollable body: description + allergens + option groups -->
      <div class="flex-1 overflow-y-auto overscroll-contain px-5 py-4 space-y-5">
        <!-- Full description -->
        <p v-if="dish.description" class="text-sm leading-relaxed text-slate-300">{{ dish.description }}</p>
        <!-- Allergen list -->
        <div v-if="dish.allergens?.length" class="flex flex-wrap gap-1.5">
          <span class="text-[10px] font-semibold uppercase tracking-widest text-slate-500 self-center shrink-0">{{ t('mktMenu.freeFrom') }}:</span>
          <span
            v-for="a in dish.allergens"
            :key="a"
            class="rounded-full border border-amber-500/30 bg-amber-500/8 px-2 py-0.5 text-[11px] font-medium text-amber-300"
          >{{ t(`mktMenu.allergen_${a}`) }}</span>
        </div>
        <!-- Divider between info and option groups (only shown when both exist) -->
        <hr v-if="(dish.description || dish.allergens?.length) && dish.option_groups?.length" class="border-slate-800/60" />
        <!-- Option groups (one per group) -->
        <div
          v-for="grp in dish.option_groups"
          :key="grp.id"
          role="group"
          :aria-labelledby="`opt-grp-${grp.id}`"
        >
          <!-- Group label + badges -->
          <div class="flex items-start justify-between gap-2 mb-3">
            <p :id="`opt-grp-${grp.id}`" class="text-sm font-semibold text-white leading-snug">{{ grp.name }}</p>
            <div class="flex items-center gap-1.5 shrink-0">
              <span
                class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                :class="grp.min_select > 0
                  ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                  : 'border-slate-700/60 bg-slate-900/60 text-slate-400'"
              >{{ grp.min_select > 0 ? t('mktMenu.optionRequired') : t('mktMenu.optionOptional') }}</span>
              <span class="text-[10px] text-slate-500 whitespace-nowrap">{{ grp.max_select === 1 ? t('mktMenu.optionChooseOne') : t('mktMenu.optionChooseUp', { max: grp.max_select }) }}</span>
            </div>
          </div>
          <!-- Option buttons -->
          <div class="space-y-2">
            <button
              v-for="opt in grp.options"
              :key="opt.id"
              type="button"
              :disabled="!opt.is_available || (!isOptionSelected(grp.id, opt.id) && isGroupAtMax(grp))"
              class="w-full flex items-center gap-3 rounded-xl border px-3.5 py-3 text-start transition-colors ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 disabled:pointer-events-none disabled:opacity-40"
              :class="isOptionSelected(grp.id, opt.id)
                ? 'border-[var(--color-secondary)]/60 bg-[var(--color-secondary)]/10 text-white'
                : 'border-slate-700/60 bg-slate-900/40 text-slate-300 hover:border-slate-600 hover:bg-slate-900/60'"
              :aria-pressed="isOptionSelected(grp.id, opt.id)"
              @click="emit('toggle', grp, opt.id)"
            >
              <!-- Indicator: filled dot for radio (single), checkmark for multi -->
              <span
                class="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full border-2 transition-all"
                :class="isOptionSelected(grp.id, opt.id)
                  ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]'
                  : 'border-slate-600'"
                aria-hidden="true"
              >
                <svg v-if="isOptionSelected(grp.id, opt.id) && grp.max_select > 1" viewBox="0 0 10 10" class="h-2.5 w-2.5 text-slate-950" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 5l2.5 2.5 3.5-4"/></svg>
                <span v-else-if="isOptionSelected(grp.id, opt.id)" class="h-2 w-2 rounded-full bg-slate-950" aria-hidden="true" />
              </span>
              <span class="flex-1 text-sm font-medium">{{ opt.name }}</span>
              <span
                v-if="Number(opt.price_delta)"
                class="shrink-0 text-xs tabular-nums"
                :class="isOptionSelected(grp.id, opt.id) ? 'text-[var(--color-secondary)]' : 'text-slate-400'"
              >{{ Number(opt.price_delta) > 0 ? '+' : '' }}{{ fmtPrice(opt.price_delta) }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Validation error shown after attempted confirm -->
      <div
        v-if="showErrors && !valid"
        class="mx-5 mb-2 flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/8 px-3 py-2"
        role="alert"
      >
        <svg aria-hidden="true" viewBox="0 0 16 16" class="h-3.5 w-3.5 shrink-0 text-rose-400" fill="currentColor">
          <path fill-rule="evenodd" d="M8 15A7 7 0 108 1a7 7 0 000 14zm-.75-9.5a.75.75 0 011.5 0v4a.75.75 0 01-1.5 0v-4zm.75 6a.875.875 0 100-1.75.875.875 0 000 1.75z" clip-rule="evenodd"/>
        </svg>
        <p class="text-xs text-rose-300">{{ t('mktMenu.optionInvalid') }}</p>
      </div>

      <!-- Footer: running unit price + Add CTA -->
      <div class="px-5 pt-3 pb-6 shrink-0 border-t border-slate-800/50">
        <button
          type="button"
          class="ui-press w-full rounded-2xl bg-[var(--color-secondary)] py-3.5 text-sm font-bold text-slate-950 transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/50"
          @click="emit('confirm')"
        >
          {{ t('mktMenu.optionConfirm', { price: fmtPrice(unitPrice) }) }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// The dish option-group selection bottom sheet of MarketplaceMenuPage.vue,
// extracted as a PRESENTATIONAL child (RISK FE-2). Non-money (it configures a cart
// item; the price shown is display-only until checkout).
//
// It owns NO selection logic: the parent keeps the selection state
// (panelSelections), the toggle/validation/running-price logic, and the add-to-cart
// confirm handler. The selection helpers (isOptionSelected / isGroupAtMax) come in
// as FUNCTION props — they read the parent's reactive panelSelections during this
// child's render, so a toggle re-renders the sheet exactly as the inline version
// did. Display helpers (fmtPrice / dishSalePrice / tagBadgeClass) and the derived
// values (flashSalePct / showErrors / valid / unitPrice) are props; option taps /
// confirm / close are emits. The initial-focus-on-open (the sheet's only use of the
// old optionPanelRef) moved in self-contained.
import { onMounted, nextTick, ref } from 'vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The dish whose option groups are being chosen (activeOptionDish). */
  dish: { type: Object, required: true },
  /** Active flash-sale percent (truthy → show the strikethrough base price). */
  flashSalePct: { type: Number, default: 0 },
  /** Whether to surface the "invalid selection" error (panelShowErrors). */
  showErrors: { type: Boolean, default: false },
  /** Whether the current selection satisfies every group's min (optionPanelValid). */
  valid: { type: Boolean, default: false },
  /** Running unit price incl. selected option deltas (optionPanelUnitPrice). */
  unitPrice: { type: Number, default: 0 },
  // ── helpers (parent-owned, passed as function props) ──
  fmtPrice: { type: Function, required: true },
  dishSalePrice: { type: Function, required: true },
  tagBadgeClass: { type: Function, required: true },
  /** (groupId, optionId) → boolean; reads the parent's panelSelections. */
  isOptionSelected: { type: Function, required: true },
  /** (group) → boolean; true when the group has hit max_select. */
  isGroupAtMax: { type: Function, required: true },
});

const emit = defineEmits(['toggle', 'confirm', 'close']);

// Move initial focus into the sheet on open (mirrors the parent's old
// openOptionPanel focus via optionPanelRef — first enabled button).
const rootRef = ref(null);
onMounted(() => nextTick(() => rootRef.value?.querySelector('button:not([disabled])')?.focus()));
</script>
