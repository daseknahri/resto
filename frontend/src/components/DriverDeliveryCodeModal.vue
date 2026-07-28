<template>
  <!-- Delivery code modal -->
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
        :aria-label="t('driver.enterDeliveryCode')"
        class="w-full max-w-sm space-y-4 rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl"
      >
        <div>
          <p class="text-sm font-semibold text-white">{{ t('driver.enterDeliveryCode') }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ t('driver.codeReminder') }}</p>
        </div>
        <input
          v-model="codeInput"
          type="text"
          inputmode="numeric"
          pattern="[0-9]*"
          class="ui-input text-center text-lg tracking-[0.3em] font-bold"
          :placeholder="t('driver.enterDeliveryCode')"
          :aria-label="t('driver.enterDeliveryCode')"
          autocomplete="one-time-code"
          maxlength="6"
          @keydown.enter="emit('submit')"
        />
        <div v-if="codeError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <p class="text-sm text-red-300">{{ codeError }}</p>
        </div>

        <!-- Photo fallback: driver can't get the code → take a photo instead -->
        <div v-if="proofPhotoPreview" class="space-y-2">
          <img :src="proofPhotoPreview" alt="" class="w-full rounded-xl object-cover" style="max-height:120px" />
          <p class="text-[11px] text-slate-400">{{ t('driver.proofPhotoReady') }}</p>
        </div>
        <div v-else class="flex items-center gap-2">
          <div class="flex-1 border-t border-slate-700/60" />
          <span class="text-[11px] text-slate-500 shrink-0">{{ t('driver.proofPhotoOr') }}</span>
          <div class="flex-1 border-t border-slate-700/60" />
        </div>
        <label
          v-if="!proofPhotoPreview"
          class="ui-touch-target flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl border border-slate-600 py-2.5 text-xs text-slate-300 hover:border-slate-400 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-slate-400"
          :class="{ 'opacity-50 pointer-events-none': submitting }"
        >
          <AppIcon name="camera" class="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
          {{ t('driver.leaveAtDoor') }}
          <input
            ref="proofPhotoInputRef"
            type="file"
            accept="image/*"
            capture="environment"
            class="sr-only"
            :disabled="submitting"
            @change="onProofPhotoSelected"
          />
        </label>
        <button
          v-else
          class="ui-touch-target w-full text-[11px] text-slate-400 hover:text-slate-200"
          @click="clearProofPhoto"
        >
          {{ t('driver.proofPhotoRetake') }}
        </button>

        <div class="flex items-center justify-end gap-2 pt-1">
          <button class="ui-btn-outline ui-press px-3 py-2 text-xs" @click="emit('close')">
            {{ t('common.cancel') }}
          </button>
          <button
            class="ui-btn-primary ui-press ui-touch-target inline-flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
            style="min-height: 48px"
            :disabled="(!codeInput.trim() && !proofPhotoFile) || submitting"
            :aria-busy="submitting"
            @click="emit('submit')"
          >
            <svg v-if="submitting" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ submitting ? t('common.loading') : t('common.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
// The proof-of-delivery code modal of DriverPage.vue, extracted as a self-contained
// drawer (RISK FE-2). The driver enters the 6-digit delivery PIN, or falls back to a
// proof photo (camera file input) when they can't get the code. Non-money.
//
// The drawer owns the whole modal (Teleport + backdrop + dialog) + its a11y focus
// trap (shared useFocusTrap, keyed on `open`), AND the self-contained photo-proof UI:
// the file input, the object-URL thumbnail lifecycle (create on select, revoke on
// clear / close / unmount) and the file-input reset. The code / error / selected-file
// STATE stays owned by the parent via two-way models — because the parent's
// submitDeliveryCode reads `codeInput` + `proofPhotoFile` and writes `codeError`
// verbatim (that critical delivery-completion path is untouched). The parent also
// keeps open/submitting state, opening (advance('delivered')) and close/return-focus.
//
// The focus trap replaces the parent's old explicit `codeFirstRef.focus()` on open —
// the code input is the dialog's first focusable, so useFocusTrap focuses it anyway.
import { ref, watch, onBeforeUnmount } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useFocusTrap } from '../composables/useFocusTrap';
import AppIcon from './AppIcon.vue';

const { t } = useI18n();

const props = defineProps({
  /** Whether the modal is open (codeModalOpen) — also the focus-trap signal. */
  open: { type: Boolean, default: false },
  /** True while the delivery-code / photo submit is in flight (codeSubmitting). */
  submitting: { type: Boolean, default: false },
});

/** The typed delivery PIN (codeInput), two-way — the parent's submit reads it. */
const codeInput = defineModel('codeInput', { type: String, default: '' });
/** The error message (codeError), two-way — the parent's submit writes it. */
const codeError = defineModel('codeError', { type: String, default: '' });
/** The selected proof-photo File (proofPhotoFile), two-way — the parent's submit reads it. */
const proofPhotoFile = defineModel('proofPhotoFile', { type: Object, default: null });

const emit = defineEmits(['close', 'submit']);

// ── Proof-photo UI (self-contained: input ref + object-URL thumbnail) ──
const proofPhotoInputRef = ref(null);
const proofPhotoPreview = ref(''); // Object URL for the in-modal thumbnail

const clearProofPhoto = () => {
  if (proofPhotoPreview.value) URL.revokeObjectURL(proofPhotoPreview.value);
  proofPhotoFile.value = null;
  proofPhotoPreview.value = '';
  if (proofPhotoInputRef.value) proofPhotoInputRef.value.value = '';
};

const onProofPhotoSelected = (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  clearProofPhoto();
  proofPhotoFile.value = file;
  proofPhotoPreview.value = URL.createObjectURL(file);
  // Clear the code input so only one proof path is active at a time.
  codeInput.value = '';
  codeError.value = '';
};

// Clear the photo when the modal closes (the parent's closeCodeModal used to do
// this); also revoke the object URL on unmount to avoid a leak.
watch(() => props.open, (open) => { if (!open) clearProofPhoto(); });
onBeforeUnmount(() => { if (proofPhotoPreview.value) URL.revokeObjectURL(proofPhotoPreview.value); });

// D-8: Tab focus-trap + open/return focus handling (shared helper), keyed on `open`.
const dialogRef = ref(null);
useFocusTrap(dialogRef, () => props.open);
</script>
