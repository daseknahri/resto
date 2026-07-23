<template>
  <div class="ui-reveal space-y-2 rounded-2xl border border-amber-500/30 bg-amber-500/8 px-4 py-3">
    <p class="text-sm font-semibold text-amber-100">{{ t('waiter.firstRunTitle') }}</p>
    <p class="text-xs text-amber-200/80">{{ t('waiter.firstRunBody') }}</p>
    <button class="ui-btn-primary ui-press px-4 py-1.5 text-xs" @click="emit('dismiss')">
      {{ t('waiter.firstRunDismiss') }}
    </button>
  </div>
</template>

<script setup>
// The one-time first-run welcome banner of WaiterPage.vue, extracted as a DUMB
// presentational child (RISK FE-2). Display only: it shows the welcome title/body
// and a dismiss button. The parent (WaiterPage.vue) owns the seen/dismiss state
// (`waiterFirstRunSeen` + localStorage) and keeps the v-if that mounts this — the
// tap just forwards intent via the `dismiss` emit.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

const emit = defineEmits(['dismiss']);
</script>
