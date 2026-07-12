<template>

  <!-- ══════════════════════════ PAST RIDES ══════════════════════════ -->
  <section v-if="history.length > 0 || loading" class="space-y-2 pt-2">
    <p class="ui-kicker px-1">{{ t('ridePage.historyTitle') }}</p>

    <!-- Loading skeleton -->
    <template v-if="loading && history.length === 0">
      <div
        v-for="n in 3"
        :key="n"
        class="h-14 w-full animate-pulse rounded-2xl bg-slate-800/60"
      />
    </template>

    <!-- History rows -->
    <ul v-else class="space-y-1.5">
      <li
        v-for="ride in history"
        :key="ride.id"
        class="ui-panel flex items-center gap-3 px-3 py-2.5"
      >
        <!-- Route: dropoff (primary) -->
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm text-slate-200">
            {{ ride.dropoff_address || ride.pickup_address }}
          </p>
          <p class="mt-0.5 truncate text-[11px] text-slate-500">
            {{ fmtDate(ride.created_at) }}
          </p>
        </div>

        <!-- Fare -->
        <span class="shrink-0 text-sm font-bold tabular-nums text-slate-200">
          {{ formatPrice(ride.fare) }}
        </span>

        <!-- Status chip -->
        <span
          class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
          :class="ride.status === 'completed'
            ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
            : 'border border-red-500/30 bg-red-500/10 text-red-300'"
        >
          {{ historyStatusLabel(ride.status) }}
        </span>

        <!-- Star rating (if rider rated the driver) -->
        <span
          v-if="ride.rider_driver_rating"
          class="shrink-0 flex items-center gap-0.5 text-amber-400"
          :aria-label="`${ride.rider_driver_rating} stars`"
        >
          <AppIcon name="star" class="h-3.5 w-3.5" aria-hidden="true" />
          <span class="text-[11px] font-semibold tabular-nums">{{ ride.rider_driver_rating }}</span>
        </span>

        <!-- Rebook — completed rides only -->
        <button
          v-if="ride.status === 'completed'"
          type="button"
          class="shrink-0 rounded-xl border border-[var(--color-secondary)]/30 bg-[var(--color-secondary)]/8 px-2.5 py-1.5 text-xs font-semibold text-[var(--color-secondary)] transition hover:bg-[var(--color-secondary)]/15 ui-press"
          :aria-label="t('ridePage.rebookAriaLabel')"
          @click="emit('rebook', ride)"
        >
          {{ t('ridePage.rebookCta') }}
        </button>
      </li>
    </ul>
  </section>

  <!-- Empty state — only show after load attempt with no results -->
  <p
    v-else-if="!loading && history.length === 0 && isAuthenticated"
    class="px-1 text-center text-xs text-slate-600"
  >
    {{ t('ridePage.historyEmpty') }}
  </p>
</template>

<script setup>
// Past-rides history section of RidePage.vue (the ride-booking flow),
// extracted as a standalone presentational component (RISK FE-2), mirroring
// SendPackageHistory.vue. Fetch/state ownership stays in the parent:
// `history` is the parent's `rideHistory` ref and `loading` is the parent's
// `historyLoading` ref, both set inside `fetchHistory()`. This component
// does no fetching and no fare/map/booking logic — it only renders whatever
// history it's given and asks the parent to rebook via the `rebook` emit;
// the parent's existing `rebookRide(ride)` (address/coords prefill, map pin
// + scroll-to-form) is unchanged.
import { useI18n } from '../composables/useI18n';
import AppIcon from './AppIcon.vue';

const { t, formatPrice, currentLocale } = useI18n();

defineProps({
  /** The customer's ride history. */
  history: { type: Array, default: () => [] },
  /** True while the parent is fetching history. */
  loading: { type: Boolean, default: false },
  /** Mirrors the parent's original empty-state guard (customerStore.isAuthenticated). */
  isAuthenticated: { type: Boolean, default: false },
});

const emit = defineEmits(['rebook']);

// ── Date helper (verbatim copy of the parent's original, display-only) ──────
const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(currentLocale.value || undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return '';
  }
};

// ── Status label for history chips (verbatim copy of the parent's original) ─
const historyStatusLabel = (status) => {
  switch (status) {
    case 'completed': return t('ridePage.completed');
    case 'cancelled': return t('ridePage.cancelled');
    default:          return status;
  }
};
</script>
