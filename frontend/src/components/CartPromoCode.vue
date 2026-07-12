<template>
  <!-- ── Promo code (collapsible) ── -->
  <div>
    <!-- Applied state -->
    <div
      v-if="promoApplied"
      class="flex items-center justify-between gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/8 px-3 py-2"
    >
      <div class="min-w-0">
        <p class="text-xs font-semibold text-emerald-300">{{ promoApplied.name }}</p>
        <p class="text-[10px] text-emerald-400/70">
          {{ promoApplied.promo_type === 'percentage'
            ? t('ownerPromotions.labelPercentage', { value: promoApplied.discount_value })
            : promoApplied.promo_type === 'fixed'
              ? t('ownerPromotions.labelFixed', { value: promoApplied.discount_value })
              : t('ownerPromotions.typeFreeDelivery') }}
        </p>
      </div>
      <button class="shrink-0 text-[10px] text-slate-400 hover:text-red-300 transition-colors" @click="emit('remove')">
        {{ t('cartPage.promoRemove') }}
      </button>
    </div>
    <!-- Collapsed toggle -->
    <template v-else>
      <button
        type="button"
        class="flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-[var(--color-secondary)] transition-colors"
        :aria-expanded="promoOpen"
        @click="emit('toggle-open')"
      >
        <AppIcon name="tag" class="h-3.5 w-3.5" aria-hidden="true" />
        {{ t('cartPage.promoCodeCta') }}
        <span aria-hidden="true" class="text-slate-600 text-[11px]">{{ promoOpen ? '▾' : '▸' }}</span>
      </button>
      <div v-show="promoOpen" class="mt-2 flex gap-2">
        <input
          :value="promoCode"
          type="text"
          maxlength="20"
          autocomplete="off"
          class="ui-input flex-1 uppercase text-sm"
          :aria-label="t('cartPage.promoCodeLabel')"
          :placeholder="t('cartPage.promoPlaceholder')"
          :aria-invalid="promoError ? 'true' : undefined"
          aria-describedby="cart-promo-error"
          @keyup.enter="emit('apply')"
          @input="emit('promo-code-input', $event.target.value)"
        />
        <button
          class="inline-flex shrink-0 items-center gap-1 rounded-xl border border-slate-600 bg-slate-800/60 px-3 py-2 text-xs font-semibold text-slate-300 hover:border-indigo-500/60 hover:text-indigo-300 transition-colors disabled:opacity-50"
          :disabled="promoChecking || !promoCode.trim()"
          :aria-busy="promoChecking"
          @click="emit('apply')"
        >
          <svg v-if="promoChecking" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ promoChecking ? t('common.loading') : t('cartPage.promoApply') }}
        </button>
      </div>
      <p v-if="promoError" id="cart-promo-error" class="mt-1 text-[10px] text-red-300">{{ promoError }}</p>
    </template>
  </div>
</template>

<script setup>
// Promo-code row of Cart.vue (customer checkout page), extracted as a
// standalone presentational component (RISK FE-2). This is DISPLAY ONLY —
// all money/discount computation, the promo-check API call, and payload
// building stay in the parent (Cart.vue). The child never reads or derives
// a discount amount; it only renders whatever `promoApplied` the parent
// already fetched and forwards user intent (toggle / type / apply / remove)
// back up via emits. `promo-code-input` deliberately forwards the RAW typed
// value (not the parent's ref) — the parent's handler is responsible for the
// same toUpperCase()+clear-error transform the original inline template did,
// so behavior is byte-for-byte identical to before extraction.
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The applied promo, or null when none is applied: { name, promo_type, discount_value }. */
  promoApplied: { type: Object, default: null },
  /** Whether the collapsed code-entry row is expanded. */
  promoOpen: { type: Boolean, default: false },
  /** Current promo code input value (owned by the parent). */
  promoCode: { type: String, default: '' },
  /** True while the parent is checking the code against the backend. */
  promoChecking: { type: Boolean, default: false },
  /** Validation/check error message to show under the input. */
  promoError: { type: String, default: '' },
});

const emit = defineEmits(['toggle-open', 'promo-code-input', 'apply', 'remove']);
</script>
