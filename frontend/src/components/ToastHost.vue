<template>
  <!-- aria-live region must always be in the DOM; content change triggers announcement -->
  <!-- TODO: requires logic change — split into polite + assertive live regions for error toasts (WCAG 4.1.3) -->
  <div
    role="status"
    aria-live="polite"
    aria-atomic="true"
    class="pointer-events-none fixed bottom-4 end-4 z-40 sm:bottom-6 sm:end-6"
  >
    <Transition name="ui-fade">
      <div
        v-if="toast.visible"
        class="ui-toast pointer-events-auto flex max-w-xs items-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3 text-sm text-slate-100 shadow-2xl shadow-black/40 sm:max-w-sm"
      >
        <!-- Type indicator — color + shape; aria-hidden because the SR text below conveys the type -->
        <span
          aria-hidden="true"
          class="h-2 w-2 shrink-0 rounded-full"
          :class="
            toast.type === 'success'
              ? 'bg-emerald-400'
              : toast.type === 'error'
                ? 'bg-rose-400'
                : 'bg-amber-300'
          "
        />
        <span class="min-w-0 flex-1 break-words">
          <span class="sr-only">{{ t(`toast.type.${toast.type}`) }} </span>{{ toast.message }}</span>
        <button
          type="button"
          class="ui-press shrink-0 rounded-lg p-1 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-slate-400"
          :aria-label="t('common.close')"
          @click="toast.hide()"
        >
          <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import AppIcon from "./AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";

const toast = useToastStore();
const { t } = useI18n();
</script>
