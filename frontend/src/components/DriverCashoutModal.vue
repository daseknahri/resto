<template>
  <!-- Cash-out amount modal -->
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
      @click.self="emit('close')"
      @keydown.esc="emit('close')"
    >
      <div
        ref="dialogRef"
        role="dialog"
        aria-modal="true"
        :aria-label="t('driver.cashOut')"
        class="w-full max-w-sm space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl"
      >
        <div>
          <p class="text-sm font-semibold text-white">{{ t('driver.cashOut') }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ t('driver.cashOutAmountPrompt', { max: fmtMoney(maxAmount ?? 0) }) }}</p>
        </div>
        <input
          v-model="amount"
          type="number"
          min="1"
          :max="maxAmount ?? undefined"
          step="0.01"
          class="ui-input text-lg font-bold tabular-nums"
          :aria-label="t('driver.cashOut')"
          @keydown.enter="emit('submit')"
        />
        <div v-if="error" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <p class="text-sm text-red-300">{{ error }}</p>
        </div>
        <div class="flex items-center justify-end gap-2 pt-1">
          <button class="ui-btn-outline ui-press px-3 py-2 text-xs" @click="emit('close')">
            {{ t('common.cancel') }}
          </button>
          <button
            class="ui-btn-primary ui-press inline-flex items-center gap-2 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="busy"
            :aria-busy="busy"
            @click="emit('submit')"
          >
            <svg v-if="busy" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ busy ? t('common.loading') : t('driver.cashOut') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
// The driver cash-out (payout) amount modal of DriverPage.vue, extracted as a
// self-contained drawer (RISK FE-2). MONEY-PATH — it owns NO payout logic: the
// amount validation + the POST /driver/cashout/ + the success/error handling stay
// in the parent's submitCashout, which reads `cashoutInput` and writes
// `cashoutModalError` verbatim (both are two-way models here). The drawer owns only
// the modal (Teleport + backdrop + dialog) and its a11y focus trap (shared
// useFocusTrap, keyed on `open`). `busy` + `maxAmount` + `fmtMoney` are props; the
// parent keeps open/return-focus and requestCashout (which seeds the amount = max).
//
// The focus trap replaces the parent's old explicit `cashoutFirstRef.focus()` on
// open — the amount input is the dialog's first focusable, so useFocusTrap focuses
// it anyway.
import { ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useFocusTrap } from '../composables/useFocusTrap';

const { t } = useI18n();

const props = defineProps({
  /** Whether the modal is open (cashoutModalOpen) — also the focus-trap signal. */
  open: { type: Boolean, default: false },
  /** True while the cash-out POST is in flight (the shared busy flag). */
  busy: { type: Boolean, default: false },
  /** Max redeemable amount (earnings.available) — the prompt + input ceiling. */
  maxAmount: { type: Number, default: null },
  /** Money formatter (fmtMoney). */
  fmtMoney: { type: Function, required: true },
});

/** The typed cash-out amount (cashoutInput), two-way — the parent's submit reads it. */
const amount = defineModel('amount', { type: [String, Number], default: '' });
/** The inline error (cashoutModalError), two-way — the parent's submit writes it. */
const error = defineModel('error', { type: String, default: '' });

const emit = defineEmits(['close', 'submit']);

// D-8: Tab focus-trap + open/return focus handling (shared helper), keyed on `open`.
const dialogRef = ref(null);
useFocusTrap(dialogRef, () => props.open);
</script>
