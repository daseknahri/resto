import { onBeforeUnmount, watch, nextTick } from "vue";

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Keyboard focus trap for modal dialogs.
 *
 * @param {Ref<HTMLElement|null>} dialogRef  - Template ref pointing to the dialog container
 * @param {Ref<boolean|any>}     openSignal  - Reactive value that is truthy when the dialog is open
 *
 * Usage:
 *   const dialogRef = ref(null);
 *   useFocusTrap(dialogRef, showModal);
 */
export function useFocusTrap(dialogRef, openSignal) {
  const trap = (e) => {
    if (!dialogRef.value || e.key !== 'Tab') return;
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

  watch(openSignal, async (open) => {
    if (open) {
      await nextTick();
      // Move focus into the dialog if it isn't already inside
      if (!dialogRef.value?.contains(document.activeElement)) {
        dialogRef.value?.querySelector(FOCUSABLE)?.focus();
      }
      document.addEventListener('keydown', trap);
    } else {
      document.removeEventListener('keydown', trap);
    }
  });

  onBeforeUnmount(() => document.removeEventListener('keydown', trap));
}
