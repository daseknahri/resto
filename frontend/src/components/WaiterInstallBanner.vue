<template>
  <div
    class="ui-reveal flex items-center gap-3 rounded-2xl border border-indigo-500/30 bg-indigo-500/8 px-4 py-3 text-xs"
    role="status"
  >
    <span class="flex-1 font-medium text-indigo-200">
      {{ canInstall ? t('waiterInstall.prompt') : t('waiterInstall.manual') }}
    </span>
    <button v-if="canInstall" class="ui-btn-primary ui-press shrink-0 px-3 py-1.5 text-[11px]" @click="emit('install')">
      {{ t('waiterInstall.cta') }}
    </button>
    <button
      class="ui-touch-target ui-press flex shrink-0 items-center justify-center rounded-full p-1.5 text-slate-400 transition-colors hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60"
      :aria-label="t('waiterInstall.dismiss')"
      @click="emit('dismiss')"
    >✕</button>
  </div>
</template>

<script setup>
// The "install the app" banner of WaiterPage.vue, extracted as a DUMB
// presentational child (RISK FE-2). Waiters work from the installed PWA, so this
// nudges them to install it (or shows manual instructions when the browser can't
// prompt). Display only: the parent (WaiterPage.vue) owns the install prompt
// (`useInstallPrompt`) + the standalone/dismissed state and keeps the v-if that
// mounts this; `canInstall` is passed in, and the two taps forward intent via the
// `install` / `dismiss` emits.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Whether the browser can show a native install prompt (canInstall). */
  canInstall: { type: Boolean, default: false },
});

const emit = defineEmits(['install', 'dismiss']);
</script>
