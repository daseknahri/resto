/**
 * Singleton text-prompt dialog composable.
 *
 * Drop-in replacement for window.prompt() that renders inside the app.
 * Returns null when the user cancels, or the entered string (possibly empty)
 * when they confirm.
 *
 * Usage:
 *   const { prompt } = usePromptModal()
 *   const value = await prompt({ title: "Suspend reason", required: false })
 *   if (value === null) return   // cancelled
 *   // proceed with value (string)
 */
import { ref } from "vue";

// Module-level singletons so every component shares one modal instance.
const visible = ref(false);
const _opts = ref({});
let _resolve = null;

export function usePromptModal() {
  /**
   * @param {{
   *   title?: string,
   *   body?: string,
   *   label?: string,
   *   placeholder?: string,
   *   initialValue?: string,
   *   required?: boolean,
   *   confirmLabel?: string,
   *   cancelLabel?: string,
   *   danger?: boolean,
   * }} opts
   * @returns {Promise<string|null>}  null = cancelled; string = confirmed value
   */
  const prompt = (opts = {}) => {
    _opts.value = opts;
    visible.value = true;
    return new Promise((resolve) => {
      _resolve = resolve;
    });
  };

  // Called by PromptModal.vue only.
  const _settle = (result) => {
    visible.value = false;
    if (_resolve) {
      _resolve(result);
      _resolve = null;
    }
  };

  return { visible, options: _opts, prompt, _settle };
}
