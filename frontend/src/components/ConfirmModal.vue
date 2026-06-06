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
          class="confirm-dialog ui-glass w-full max-w-sm"
        >
          <!-- Header -->
          <div class="border-b px-5 py-4" style="border-color: var(--color-border)">
            <h2 :id="dialogTitleId" class="text-base font-semibold text-slate-100">
              {{ modal.options.value.title || t("confirmModal.defaultTitle") }}
            </h2>
          </div>

          <!-- Body -->
          <div class="px-5 py-4">
            <p :id="dialogBodyId" class="ui-subtle">
              {{ modal.options.value.body || t("confirmModal.defaultBody") }}
            </p>
          </div>

          <!-- Actions -->
          <div class="flex items-center justify-end gap-3 border-t px-5 py-3" style="border-color: var(--color-border)">
            <button
              ref="cancelBtnRef"
              class="ui-btn-outline ui-touch-target px-4 text-sm"
              @click="cancel"
            >
              {{ modal.options.value.cancelLabel || t("common.cancel") }}
            </button>
            <button
              class="ui-btn-primary ui-touch-target px-4 text-sm"
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
/* Backdrop fade */
.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity var(--motion-fast, 180ms) ease;
}
.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}

/* Dialog panel scale + fade entry */
.confirm-fade-enter-active .confirm-dialog {
  transition:
    opacity var(--motion-base, 260ms) var(--ease-fluid, cubic-bezier(0.22, 1, 0.36, 1)),
    transform var(--motion-base, 260ms) var(--ease-fluid, cubic-bezier(0.22, 1, 0.36, 1));
}
.confirm-fade-leave-active .confirm-dialog {
  transition:
    opacity var(--motion-fast, 180ms) ease,
    transform var(--motion-fast, 180ms) ease;
}
.confirm-fade-enter-from .confirm-dialog {
  opacity: 0;
  transform: scale(0.94) translateY(8px);
}
.confirm-fade-leave-to .confirm-dialog {
  opacity: 0;
  transform: scale(0.96);
}

/* Respect prefers-reduced-motion: suppress transform, keep opacity */
@media (prefers-reduced-motion: reduce) {
  .confirm-fade-enter-active .confirm-dialog,
  .confirm-fade-leave-active .confirm-dialog {
    transition: opacity var(--motion-fast, 180ms) ease;
  }
  .confirm-fade-enter-from .confirm-dialog,
  .confirm-fade-leave-to .confirm-dialog {
    transform: none;
  }
}
</style>
