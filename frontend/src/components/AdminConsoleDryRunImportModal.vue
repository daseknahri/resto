<template>
  <!-- Dry-run import review modal -->
  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0"
      leave-active-class="transition-all duration-150"
      leave-to-class="opacity-0"
    >
      <div
        v-if="review"
        tabindex="-1"
        class="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-4"
        @click.self="emit('cancel')"
        @keydown.esc="emit('cancel')"
      >
        <div ref="dialogRef" role="dialog" aria-modal="true" aria-labelledby="admin-console-dry-run-dialog-title" class="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl">
          <div class="border-b border-slate-800 px-5 py-4">
            <p class="text-xs font-semibold uppercase tracking-wider text-amber-400">{{ t('adminConsole.dryRunSuccessful') }}</p>
            <h3 id="admin-console-dry-run-dialog-title" class="mt-1 text-base font-semibold text-white">{{ t('adminConsole.applyImportNow') }}</h3>
          </div>
          <div class="px-5 py-4 space-y-2 text-sm text-slate-300">
            <div class="flex justify-between"><span class="text-slate-500">{{ t('common.categories') }}</span><span class="font-semibold">{{ review.summary.categories || 0 }}</span></div>
            <div class="flex justify-between"><span class="text-slate-500">{{ t('common.dishes') }}</span><span class="font-semibold">{{ review.summary.dishes || 0 }}</span></div>
            <div class="flex justify-between"><span class="text-slate-500">{{ t('adminConsole.optionsLabel') }}</span><span class="font-semibold">{{ review.summary.options || 0 }}</span></div>
            <div class="flex justify-between"><span class="text-slate-500">{{ t('adminConsole.tableLinksLabel') }}</span><span class="font-semibold">{{ review.summary.table_links || 0 }}</span></div>
            <div class="flex justify-between"><span class="text-slate-500">{{ t('adminConsole.profileLabel') }}</span><span class="font-semibold" :class="review.summary.profile_updated ? 'text-emerald-400' : 'text-slate-500'">{{ review.summary.profile_updated ? t('adminConsole.yes') : t('adminConsole.no') }}</span></div>
          </div>
          <div class="flex items-center justify-end gap-3 border-t border-slate-800 px-5 py-4">
            <button
              class="ui-btn-outline ui-press px-4 py-2 text-sm disabled:opacity-50"
              :disabled="applying"
              @click="emit('cancel')"
            >{{ t('common.cancel') }}</button>
            <button
              class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
              :disabled="applying"
              :aria-busy="applying"
              @click="emit('apply')"
            >
              <svg v-if="applying" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ applying ? t('common.loading') : t('adminConsole.applyImport') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
// "Dry-run import review" modal of AdminConsole.vue, extracted as a standalone
// child component (RISK FE-2). The import dry-run/apply flow stays owned by the
// parent: the parent builds the review object (tenant + summary + replaceBody)
// from the settings-import dry-run response, and its `cancel`/`apply` handlers
// keep the toast + settings-import API call. This component is purely
// presentational — it renders the summary it's given and asks the parent to
// cancel or apply via emits. The focus trap is directly-supporting a11y logic
// for this dialog, so it lives here (self-contained: its own dialog ref +
// keydown listener, cleaned up on unmount) the same way the parent owned it
// before the extraction.
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "../composables/useI18n";

const props = defineProps({
  /** The dry-run review to display ({ tenant, summary, replaceBody }); null = closed.
   * Only `summary` is rendered here — `tenant`/`replaceBody` are the parent's to apply. */
  review: { type: Object, default: null },
  /** True while the parent's apply-import request is in flight (drives the spinner + disabled state). */
  applying: { type: Boolean, default: false },
});

const emit = defineEmits(["cancel", "apply"]);

const { t } = useI18n();

const dialogRef = ref(null);

const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapFocus = (e) => {
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

watch(() => props.review, async (val) => {
  if (val) {
    await nextTick();
    dialogRef.value?.querySelector(FOCUSABLE)?.focus();
    document.addEventListener('keydown', trapFocus);
  } else {
    document.removeEventListener('keydown', trapFocus);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('keydown', trapFocus);
});
</script>
