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
        class="ui-toast ui-panel pointer-events-auto flex max-w-xs items-center gap-3 px-4 py-3 text-sm text-slate-100 shadow-2xl shadow-black/40 sm:max-w-sm"
      >
        <!-- Type indicator dot — color conveys semantic type; aria-hidden because sr-only text below covers it -->
        <!-- Intentional semantic color overrides: emerald=success, rose=error, amber=warn/info -->
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
        class="ui-toast ui-panel pointer-events-auto flex max-w-xs items-center gap-3 px-4 py-3 text-sm text-slate-100 shadow-2xl shadow-black/40 sm:max-w-sm"
      >
        <!-- Type indicator dot — intentional semantic color override: rose=error -->
        <span
          aria-hidden="true"
          class="h-2 w-2 shrink-0 rounded-full bg-rose-400"
        />
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
