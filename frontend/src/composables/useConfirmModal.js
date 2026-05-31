/**
 * Singleton confirm-dialog composable.
 *
 * Usage:
 *   const { confirm } = useConfirmModal()
 *   const ok = await confirm({ title: "Delete promo?", body: "This cannot be undone." })
 *   if (!ok) return
 *   // proceed with destructive action
 */
import { ref } from "vue";

// Module-level singletons so every component shares one modal instance.
const visible = ref(false);
const _opts = ref({});
let _resolve = null;

export function useConfirmModal() {
  /**
   * @param {{ title?: string, body?: string, confirmLabel?: string, cancelLabel?: string, danger?: boolean }} opts
   * @returns {Promise<boolean>}
   */
  const confirm = (opts = {}) => {
    _opts.value = opts;
    visible.value = true;
    return new Promise((resolve) => {
      _resolve = resolve;
    });
  };

  // Called by ConfirmModal.vue only.
  const _settle = (result) => {
    visible.value = false;
    if (_resolve) {
      _resolve(result);
      _resolve = null;
    }
  };

  return { visible, options: _opts, confirm, _settle };
}
