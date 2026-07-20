<template>
  <!-- Offline / queue indicator -->
  <Transition name="ui-fade">
    <div
      v-if="!online || queueLength > 0"
      class="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2 text-xs text-amber-300"
      role="status"
      aria-live="polite"
    >
      <svg aria-hidden="true" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0">
        <path fill-rule="evenodd" d="M6.701 2.25c.577-1 2.02-1 2.598 0l5.196 9a1.5 1.5 0 0 1-1.299 2.25H2.804a1.5 1.5 0 0 1-1.3-2.25l5.197-9ZM8 4a.75.75 0 0 1 .75.75v3a.75.75 0 0 1-1.5 0v-3A.75.75 0 0 1 8 4Zm0 7a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z" clip-rule="evenodd"/>
      </svg>
      <span v-if="!online">{{ t('waiterPage.offline') }}</span>
      <span v-else>{{ t('waiterPage.syncingQueue', { n: queueLength }) }}</span>
    </div>
  </Transition>
</template>

<script setup>
// Offline / queue-sync indicator of WaiterPage.vue, extracted as a standalone
// presentational child (RISK FE-2). Display only: it shows an "offline" banner
// when the waiter is disconnected, or a "syncing N queued" banner when there are
// offline-queued actions. The connectivity state + the offline queue stay owned
// by the parent's waiter store; this component just renders the current state.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Whether the waiter client is online (waiter.isOnline). */
  online: { type: Boolean, default: true },
  /** Number of actions waiting in the offline queue (waiter.offlineQueue.length). */
  queueLength: { type: Number, default: 0 },
});
</script>
