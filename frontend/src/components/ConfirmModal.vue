<template>
  <Teleport to="body">
    <Transition name="confirm-fade">
      <div
        v-if="modal.visible.value"
        class="fixed inset-0 z-[200] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        role="presentation"
        @click.self="cancel"
        @keydown.esc="cancel"
      >
        <div
          ref="dialogRef"
          role="alertdialog"
          aria-modal="true"
          :aria-labelledby="dialogTitleId"
          :aria-describedby="modal.options.value.body ? dialogBodyId : undefined"
          class="w-full max-w-sm rounded-2xl border border-slate-700/70 bg-slate-900 shadow-2xl shadow-black/60"
        >
          <!-- Header -->
          <div class="border-b border-slate-800 px-5 py-4">
            <h2 :id="dialogTitleId" class="text-base font-semibold text-slate-100">
              {{ modal.options.value.title || t("confirmModal.defaultTitle") }}
            </h2>
          </div>

          <!-- Body -->
          <div class="px-5 py-4">
            <p :id="dialogBodyId" class="text-sm text-slate-300">
              {{ modal.options.value.body || t("confirmModal.defaultBody") }}
            </p>
          </div>

          <!-- Actions -->
          <div class="flex items-center justify-end gap-3 border-t border-slate-800 px-5 py-3">
            <button
              ref="cancelBtnRef"
              class="ui-btn-outline px-4 py-1.5 text-sm"
              @click="cancel"
            >
              {{ modal.options.value.cancelLabel || t("common.cancel") }}
            </button>
            <button
              class="ui-btn-primary px-4 py-1.5 text-sm"
              :class="modal.options.value.danger !== false ? 'bg-red-600 hover:bg-red-500 border-red-600 hover:border-red-500' : ''"
              @click="ok"
            >
              {{ modal.options.value.confirmLabel || t("confirmModal.confirmBtn") }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from "vue";
import { useI18n } from "../composables/useI18n";
import { useConfirmModal } from "../composables/useConfirmModal";

const { t } = useI18n();
const modal = useConfirmModal();

const dialogTitleId = "confirm-modal-title";
const dialogBodyId  = "confirm-modal-body";

const cancelBtnRef = ref(null);
const dialogRef    = ref(null);

// ── Focus trap ──────────────────────────────────────────────────────────────
const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapFocus = (e) => {
  if (!dialogRef.value) return;
  const focusable = Array.from(dialogRef.value.querySelectorAll(FOCUSABLE));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.key !== 'Tab') return;
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

// Focus the cancel button when the modal opens; install / remove focus trap.
watch(
  () => modal.visible.value,
  async (open) => {
    if (open) {
      await nextTick();
      cancelBtnRef.value?.focus();
      document.addEventListener('keydown', trapFocus);
    } else {
      document.removeEventListener('keydown', trapFocus);
    }
  }
);

onBeforeUnmount(() => document.removeEventListener('keydown', trapFocus));

const ok     = () => modal._settle(true);
const cancel = () => modal._settle(false);
</script>

<style scoped>
.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 160ms ease;
}
.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}
</style>
