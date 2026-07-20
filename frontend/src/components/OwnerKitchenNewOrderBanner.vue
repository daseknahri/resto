<template>
  <!-- New-order flash banner (supplements audio alert in noisy kitchens) -->
  <Transition name="kitchen-flash">
    <div
      v-if="show"
      class="kitchen-new-order-banner"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span class="h-2.5 w-2.5 rounded-full bg-amber-300 animate-ping" aria-hidden="true" />
      {{ t('kitchen.newOrderAlert') }}
    </div>
  </Transition>
</template>

<script setup>
// New-order flash banner of OwnerKitchen.vue, extracted as a standalone
// presentational child (RISK FE-2). Display only: a transient status banner that
// supplements the audio alert in noisy kitchens. The `newOrderFlash` trigger
// (the timer that raises and clears it) stays owned by the parent, which passes
// its current value in as `show`; this component just renders the banner (with
// its enter/leave transition) while `show` is true. No emits, no state, no API.
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Whether the new-order flash banner is currently showing (parent-owned). */
  show: { type: Boolean, default: false },
});
</script>
