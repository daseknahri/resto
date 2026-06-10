<template>
  <Teleport to="body">
    <Transition name="confirm-fade">
      <div
        v-if="modal.visible.value"
        class="fixed inset-0 z-[200] flex items-center justify-center p-4 backdrop-blur-sm"
        style="background-color: var(--color-overlay)"
        role="presentation"
        @click.self="cancel"
      >
        <form
          ref="dialogRef"
          role="dialog"
          aria-modal="true"
          tabindex="-1"
          :aria-labelledby="dialogTitleId"
          class="confirm-dialog ui-glass w-full max-w-sm"
          @submit.prevent="ok"
        >
          <!-- Header -->
          <div class="border-b border-slate-800 px-5 py-4">
            <h2 :id="dialogTitleId" class="text-base font-semibold text-slate-100">
              {{ modal.options.value.title || t("confirmModal.defaultTitle") }}
            </h2>
            <p v-if="modal.options.value.body" class="mt-1 text-sm text-slate-400">
              {{ modal.options.value.body }}
            </p>
          </div>

          <!-- Input -->
          <div class="px-5 py-4 space-y-1.5">
            <label
              v-if="modal.options.value.label"
              :for="inputId"
              class="block text-xs font-medium text-slate-300"
            >
              {{ modal.options.value.label }}
              <span v-if="modal.options.value.required" class="text-red-400 ms-0.5" aria-hidden="true">*</span>
            </label>
            <input
              :id="inputId"
              ref="inputRef"
              v-model="inputValue"
              type="text"
              class="ui-input w-full"
              :placeholder="modal.options.value.placeholder || ''"
              :required="modal.options.value.required"
              autocomplete="off"
            />
            <p v-if="validationMsg" class="text-xs text-red-400">{{ validationMsg }}</p>
          </div>

          <!-- Actions -->
          <div class="flex items-center justify-end gap-3 border-t border-slate-800 px-5 py-3">
            <button
              ref="cancelBtnRef"
              type="button"
              class="ui-btn-outline ui-touch-target px-4 text-sm"
              @click="cancel"
            >
              {{ modal.options.value.cancelLabel || t("common.cancel") }}
            </button>
            <button
              type="submit"
              class="ui-touch-target px-4 text-sm"
              :class="modal.options.value.danger ? 'ui-btn-danger' : 'ui-btn-primary'"
            >
              {{ modal.options.value.confirmLabel || t("confirmModal.confirmBtn") }}
            </button>
          </div>
        </form>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from "vue";
import { useI18n } from "../composables/useI18n";
import { usePromptModal } from "../composables/usePromptModal";

const { t } = useI18n();
const modal = usePromptModal();

const dialogTitleId = "prompt-modal-title";
const inputId       = "prompt-modal-input";

const inputRef     = ref(null);
const cancelBtnRef = ref(null);
const dialogRef    = ref(null);
const inputValue   = ref("");
const validationMsg = ref("");

// ── Focus trap ──────────────────────────────────────────────────────────────
const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapFocus = (e) => {
  if (!dialogRef.value) return;
  if (e.key === 'Escape') { e.preventDefault(); cancel(); return; }
  if (e.key !== 'Tab') return;
  const focusable = Array.from(dialogRef.value.querySelectorAll(FOCUSABLE));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

let previouslyFocused = null;
watch(
  () => modal.visible.value,
  async (open) => {
    if (open) {
      previouslyFocused = document.activeElement;
      inputValue.value = modal.options.value.initialValue || "";
      validationMsg.value = "";
      await nextTick();
      inputRef.value?.focus();
      document.addEventListener('keydown', trapFocus);
    } else {
      document.removeEventListener('keydown', trapFocus);
      previouslyFocused?.focus();
      previouslyFocused = null;
    }
  }
);

onBeforeUnmount(() => document.removeEventListener('keydown', trapFocus));

const ok = () => {
  const val = inputValue.value.trim();
  if (modal.options.value.required && !val) {
    validationMsg.value = t("promptModal.fieldRequired");
    inputRef.value?.focus();
    return;
  }
  modal._settle(val);
};

const cancel = () => modal._settle(null);
</script>

<style scoped>
/* Reuse same transition as ConfirmModal */
.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity var(--motion-fast, 180ms) ease;
}
.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}
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
