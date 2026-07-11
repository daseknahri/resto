<template>
  <div class="ui-panel overflow-hidden p-0">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2 border-b border-slate-800/70 px-4 py-3">
      <div>
        <p class="ui-kicker">{{ t('customerAccount.reservationsTitle') }}</p>
        <p class="mt-0.5 text-[10px] text-slate-500">{{ t('customerAccount.reservationsHint') }}</p>
      </div>
      <span v-if="reservations.length" class="rounded-full border border-slate-700/60 bg-slate-900/50 px-2 py-0.5 text-[11px] tabular-nums text-slate-400">{{ reservations.length }}</span>
    </div>

    <!-- Content -->
    <div class="p-4 space-y-2">
      <!-- Loading skeleton -->
      <div v-if="loading" class="space-y-2">
        <div v-for="i in 3" :key="i" class="h-14 animate-pulse rounded-xl bg-slate-800/50" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-xs text-red-300">{{ t('customerAccount.fetchError') }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-2.5 py-1 text-[10px] font-semibold text-red-300 transition hover:bg-red-500/10"
          @click="emit('retry')"
        >{{ t('common.retry') }}</button>
      </div>

      <!-- Empty state -->
      <div v-else-if="!reservations.length" class="py-6 text-center">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" class="mx-auto mb-3 h-8 w-8 text-slate-700" aria-hidden="true">
          <path d="M7 3v4M17 3v4M4 8h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1" /><path d="M9 15l2 2 4-4" />
        </svg>
        <p class="text-sm font-medium text-slate-500">{{ t('customerAccount.reservationsEmpty') }}</p>
        <p class="mt-1 text-[11px] text-slate-600">{{ t('customerAccount.reservationsEmptyHint') }}</p>
      </div>

      <!-- Reservation list -->
      <ul v-else class="divide-y divide-slate-800/60 -mx-4 -mb-4">
        <li
          v-for="res in reservations"
          :key="res.id"
          class="flex items-start justify-between gap-3 px-4 py-3"
        >
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-semibold text-slate-200">{{ res.restaurant_name || res.restaurant_slug }}</p>
            <p class="mt-0.5 text-[11px] text-slate-400">{{ formatReservationDateTime(res.booked_for) }}</p>
            <p class="mt-0.5 text-[10px] text-slate-500">
              {{ res.party_size === 1 ? t('customerAccount.reservationPartySizeSingle') : t('customerAccount.reservationPartySize', { n: res.party_size }) }}
              <template v-if="res.notes"> · <span class="italic">{{ res.notes }}</span></template>
            </p>
          </div>
          <div class="flex shrink-0 flex-col items-end gap-1.5">
            <span
              class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
              :class="reservationStatusClass(res.status)"
            >{{ reservationStatusLabel(res.status) }}</span>
            <RouterLink
              v-if="res.cancel_token && res.restaurant_slug"
              :to="{ name: 'reservation-manage', params: { token: res.cancel_token } }"
              class="text-[10px] text-[var(--color-secondary)]/70 hover:text-[var(--color-secondary)] transition-colors"
            >{{ t('customerAccount.reservationManageLink') }} →</RouterLink>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
// Reservations tab of CustomerAccount.vue, extracted as a standalone child
// component (RISK FE-2). Fetch/state lives in the parent (CustomerAccount.vue) —
// this component is purely presentational: it renders the reservation list for
// whatever data the parent passes in, and asks the parent to retry the fetch
// on error via the `retry` emit.
import { RouterLink } from 'vue-router';
import { useI18n } from '../composables/useI18n';

const { t, currentLocale } = useI18n();

defineProps({
  /** Reservations for the signed-in customer, across all restaurants. */
  reservations: { type: Array, default: () => [] },
  /** True while the parent is fetching reservations. */
  loading: { type: Boolean, default: false },
  /** True when the parent's fetch failed. */
  error: { type: Boolean, default: false },
});

const emit = defineEmits(['retry']);

// Reservation status label map
const RESERVATION_STATUS_I18N = {
  new:        'customerAccount.reservationStatusNew',
  contacted:  'customerAccount.reservationStatusContacted',
  won:        'customerAccount.reservationStatusWon',
  lost:       'customerAccount.reservationStatusLost',
  no_show:    'customerAccount.reservationStatusNoShow',
};
const reservationStatusLabel  = (s) => t(RESERVATION_STATUS_I18N[s] || 'customerAccount.reservationStatusNew');
const reservationStatusClass  = (s) => ({
  new:       'bg-sky-500/10 text-sky-300 border-sky-500/25',
  contacted: 'bg-sky-500/10 text-sky-300 border-sky-500/25',
  won:       'bg-emerald-500/10 text-emerald-300 border-emerald-500/25',
  lost:      'bg-slate-700/40 text-slate-400 border-slate-600/30',
  no_show:   'bg-amber-500/10 text-amber-300 border-amber-500/25',
}[s] || 'bg-slate-700/40 text-slate-400 border-slate-600/30');

const formatReservationDateTime = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch { return iso; }
};
</script>
