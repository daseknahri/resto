<template>
  <!-- Two always-in-DOM live regions: polite for info/success/warning, assertive for error -->
  <!-- Polite region: info, success, warning -->
  <div
    role="status"
    aria-live="polite"
    aria-atomic="true"
    class="pointer-events-none fixed end-4 z-40 sm:end-6"
    style="bottom: calc(var(--safe-bottom) + 1rem)"
  >
    <Transition name="ui-fade">
      <div
        v-if="toast.visible && toast.type !== 'error'"
        class="ui-toast pointer-events-auto relative flex max-w-xs items-center gap-3 overflow-hidden rounded-2xl border px-4 py-3 text-sm text-slate-100 shadow-2xl shadow-black/40 backdrop-blur-xl sm:max-w-sm"
        :class="
          toast.type === 'success'
            ? 'border-emerald-500/40 bg-slate-900/95'
            : 'border-amber-500/35 bg-slate-900/95'
        "
      >
        <!-- Left accent bar -->
        <div
          aria-hidden="true"
          class="pointer-events-none absolute inset-y-0 start-0 w-[3px] rounded-s-2xl"
          :class="toast.type === 'success' ? 'bg-emerald-400' : 'bg-amber-400'"
        />
        <!-- Icon -->
        <!-- success: check circle; info/warning: info circle -->
        <span
          aria-hidden="true"
          class="ms-1 shrink-0"
          :class="toast.type === 'success' ? 'text-emerald-400' : 'text-amber-400'"
        >
          <svg v-if="toast.type === 'success'" viewBox="0 0 20 20" class="h-5 w-5 fill-current">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
          </svg>
          <svg v-else viewBox="0 0 20 20" class="h-5 w-5 fill-current">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
          </svg>
        </span>
        <span class="min-w-0 flex-1 break-words">
          <span class="sr-only">{{ t(`toast.type.${toast.type}`) }} </span>{{ toast.message }}</span>
        <button
          type="button"
          class="ui-touch-target ui-press shrink-0 rounded-lg text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-slate-400"
          :aria-label="t('common.close')"
          @click="toast.hide()"
        >
          <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </Transition>
  </div>

  <!-- Assertive region: error toasts only — interrupts immediately (WCAG 4.1.3) -->
  <div
    role="alert"
    aria-live="assertive"
    aria-atomic="true"
    class="pointer-events-none fixed end-4 z-40 sm:end-6"
    style="bottom: calc(var(--safe-bottom) + 1rem)"
  >
    <Transition name="ui-fade">
      <div
        v-if="toast.visible && toast.type === 'error'"
        class="ui-toast pointer-events-auto relative flex max-w-xs items-center gap-3 overflow-hidden rounded-2xl border border-rose-500/40 bg-slate-900/95 px-4 py-3 text-sm text-slate-100 shadow-2xl shadow-black/40 backdrop-blur-xl sm:max-w-sm"
      >
        <!-- Left accent bar -->
        <div aria-hidden="true" class="pointer-events-none absolute inset-y-0 start-0 w-[3px] rounded-s-2xl bg-rose-400" />
        <!-- Error icon -->
        <span aria-hidden="true" class="ms-1 shrink-0 text-rose-400">
          <svg viewBox="0 0 20 20" class="h-5 w-5 fill-current">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
        </span>
        <span class="min-w-0 flex-1 break-words">
          <span class="sr-only">{{ t(`toast.type.${toast.type}`) }} </span>{{ toast.message }}</span>
        <button
          type="button"
          class="ui-touch-target ui-press shrink-0 rounded-lg text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-slate-400"
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
