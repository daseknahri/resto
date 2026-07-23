<template>
  <!-- Selected calendar reservation detail (quick panel) -->
  <div class="ui-panel ui-reveal p-4 space-y-2.5 text-sm">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="truncate font-bold text-white leading-snug">{{ reservation.name }}</p>
        <p class="truncate text-xs text-slate-400 mt-0.5">{{ reservation.phone }} · {{ reservation.email }}</p>
      </div>
      <button
        class="ui-press shrink-0 rounded-lg p-1.5 text-slate-500 transition hover:bg-slate-800/60 hover:text-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/60"
        :aria-label="t('common.close')"
        @click="emit('close')"
      >
        <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
    <p v-if="reservation.booked_for" class="text-xs text-slate-300 tabular-nums">
      {{ t("ownerReservations.bookedFor") }}: {{ formatDateTime(reservation.booked_for) }}
      <span v-if="reservation.party_size"> · {{ reservation.party_size }} {{ t("ownerReservations.guests") }}</span>
    </p>
    <p v-if="reservation.notes" class="rounded-xl border border-slate-800/80 bg-slate-950/50 px-3 py-2.5 text-xs text-slate-300 whitespace-pre-line leading-relaxed">{{ reservation.notes }}</p>
  </div>
</template>

<script setup>
// "Selected calendar reservation detail" quick panel of OwnerReservations.vue,
// extracted as a standalone presentational child (RISK FE-2). This is DISPLAY
// ONLY — it renders the calendar reservation the parent has selected (name,
// phone/email, booked-for date + party size, and any note) and asks the parent
// to close it via the `close` emit. It makes no API calls and mutates nothing.
//
// The `viewMode === 'calendar' && selectedCalendarRes` render gate stays in the
// parent, which conditionally renders this component and owns `selectedCalendarRes`
// (cleared by the parent when `close` is emitted). `formatDateTime` is passed
// down as a function prop (same convention as OwnerReservationsWaitlist's
// `formatDate`) so date formatting stays single-sourced in the parent — note it
// is the raw `formatDateTime` from the parent's useI18n, not the `formatDate`
// wrapper, matching the original quick-panel markup byte-for-byte.
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** The selected calendar reservation to display (name, phone, email, booked_for, party_size, notes). */
  reservation: { type: Object, required: true },
  /** Locale-aware date-time formatter, owned by the parent (raw useI18n formatDateTime). */
  formatDateTime: { type: Function, required: true },
});

const emit = defineEmits(['close']);
</script>
