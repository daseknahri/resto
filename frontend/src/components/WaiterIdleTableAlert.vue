<template>
  <div
    class="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
    role="alert"
  >
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true"><path d="M8 2 1.5 13h13L8 2Zm0 4v3.5M8 11.5h.01"/></svg>
    <p class="min-w-0 flex-1 text-[11px] leading-snug text-red-300">
      {{ t('waiterPage.idleAlert', { n: tiles.length }) }}:
      <span class="font-semibold">{{ tiles.map(tile => tile.tableLabel).join(', ') }}</span>
    </p>
    <button
      class="ui-press shrink-0 text-red-400/60 hover:text-red-300 focus-visible:outline-none"
      :aria-label="t('common.dismiss')"
      @click="emit('dismiss')"
    >
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" class="h-3.5 w-3.5" aria-hidden="true"><path d="M3 3l10 10M13 3 3 13"/></svg>
    </button>
  </div>
</template>

<script setup>
// The idle-table alert banner of WaiterPage.vue's floor view, extracted as a DUMB
// presentational child (RISK FE-2). It warns that N tables have been waiting >= 20
// min and lists their labels. Display + emit only: the parent (WaiterPage.vue)
// owns the urgent-tile computation + the dismissed state and keeps the mounting
// v-if (`urgentFloorTiles.length > 0 && !idleAlertDismissed`) + the fade
// Transition; the ✕ tap forwards intent via the `dismiss` emit.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The urgent (idle) floor tiles, each with a `tableLabel` (urgentFloorTiles). */
  tiles: { type: Array, default: () => [] },
});

const emit = defineEmits(['dismiss']);
</script>
