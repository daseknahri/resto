<template>
  <!-- ── Waitlist ─────────────────────────────────────────────────────────── -->
  <section class="ui-command-deck ui-reveal space-y-3 sm:space-y-4">
    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="space-y-1">
        <p class="ui-kicker">{{ t("ownerReservations.waitlistKicker") }}</p>
        <h2 class="text-base font-bold tracking-tight text-white">{{ t("ownerReservations.waitlistTitle") }}</h2>
        <p class="text-xs text-slate-400 leading-relaxed">{{ t("ownerReservations.waitlistSubtitle") }}</p>
      </div>
      <label class="shrink-0 text-xs text-slate-400">
        <span class="sr-only">{{ t("ownerReservations.waitlistDate") }}</span>
        <input
          :value="date"
          type="date"
          class="ui-input mt-0.5 text-sm"
          :aria-label="t('ownerReservations.waitlistDate')"
          @input="emit('update:date', $event.target.value)"
          @change="emit('refresh')"
        />
      </label>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-2 py-2">
      <div v-for="i in 3" :key="i" class="h-10 animate-pulse rounded-xl bg-slate-800/50" />
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t("ownerReservations.waitlistLoadError") }}</p>
      <button
        class="ui-press shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="emit('refresh')"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!entries.length" class="ui-empty-state space-y-3 py-8 text-center">
      <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-xl border border-slate-700/80 bg-slate-950/70 text-slate-400">
        <AppIcon name="calendar" class="h-5 w-5" aria-hidden="true" />
      </div>
      <p class="text-sm text-slate-400">{{ date ? t("ownerReservations.waitlistEmpty") : t("ownerReservations.waitlistEmptyAll") }}</p>
    </div>

    <!-- Table (desktop) -->
    <div v-else class="hidden md:block ui-table-wrap rounded-xl border border-slate-700/50">
      <table class="w-full min-w-[560px] text-sm">
        <thead>
          <tr class="border-b border-slate-700/50 bg-slate-900/70 text-xs text-slate-400">
            <th scope="col" class="px-4 py-3 text-start font-semibold uppercase tracking-wide">{{ t("ownerReservations.bookedFor") }}</th>
            <th scope="col" class="px-4 py-3 text-start font-semibold uppercase tracking-wide">{{ t("common.name") }}</th>
            <th scope="col" class="px-4 py-3 text-start font-semibold uppercase tracking-wide">{{ t("ownerReservations.guests") }}</th>
            <th scope="col" class="px-4 py-3 text-start font-semibold uppercase tracking-wide">{{ t("common.status") }}</th>
            <th scope="col" class="px-4 py-3 text-start font-semibold uppercase tracking-wide">{{ t("ownerReservations.notes") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in entries"
            :key="entry.id"
            class="border-b border-slate-800/60 transition-colors hover:bg-slate-800/30"
          >
            <td class="px-4 py-3 text-slate-200 tabular-nums text-xs font-medium">{{ formatDate(entry.booked_for) }}</td>
            <td class="px-4 py-3">
              <p class="font-semibold text-slate-100">{{ entry.name }}</p>
              <p v-if="entry.phone" class="text-xs text-slate-500 tabular-nums">{{ entry.phone }}</p>
              <p v-if="entry.email" class="text-xs text-slate-500">{{ entry.email }}</p>
            </td>
            <td class="px-4 py-3 text-slate-300 tabular-nums">{{ t("ownerReservations.waitlistParty", { n: entry.party_size }) }}</td>
            <td class="px-4 py-3">
              <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold" :class="waitlistStatusClass(entry.status)">
                {{ waitlistStatusLabel(entry.status) }}
              </span>
            </td>
            <td class="max-w-[12rem] truncate px-4 py-3 text-xs text-slate-400" :title="entry.notes || undefined">{{ entry.notes || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Card list (mobile) -->
    <div v-if="entries.length" class="md:hidden space-y-2">
      <article
        v-for="entry in entries"
        :key="entry.id"
        class="ui-panel-soft space-y-2 p-3 text-sm"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate font-semibold text-slate-100">{{ entry.name }}</p>
            <p v-if="entry.phone" class="text-xs text-slate-500 tabular-nums">{{ entry.phone }}</p>
            <p v-if="entry.email" class="truncate text-xs text-slate-500">{{ entry.email }}</p>
          </div>
          <span class="shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold" :class="waitlistStatusClass(entry.status)">
            {{ waitlistStatusLabel(entry.status) }}
          </span>
        </div>
        <div class="flex flex-wrap gap-1.5 text-xs text-slate-300">
          <span class="ui-data-strip tabular-nums">{{ t("ownerReservations.bookedFor") }}: {{ formatDate(entry.booked_for) }}</span>
          <span class="ui-data-strip tabular-nums">{{ t("ownerReservations.waitlistParty", { n: entry.party_size }) }}</span>
        </div>
        <p v-if="entry.notes" class="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2.5 py-2 text-xs text-slate-400 leading-relaxed">{{ entry.notes }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
// Waitlist section of OwnerReservations.vue, extracted as a standalone
// presentational child (RISK FE-2). Fetch/date-filter state (waitlistDate,
// waitlistLoading, waitlistError, waitlistEntries) and the actual fetchWaitlist
// API call all stay owned by the parent (also driven from onMounted/onActivated)
// — this component only renders whatever page of the waitlist the parent has
// loaded, and asks the parent to update the date / re-fetch via emits.
//
// The date input mirrors the original v-model + @change split exactly: every
// keystroke emits `update:date` (so the input stays controlled from the
// parent), while only the native `change` event (date fully committed) or the
// retry button emits `refresh` — matching the original's
// `@change="fetchWaitlist"` timing precisely (no debounce/fetch-per-keystroke
// behavior change).
//
// `formatDate` is passed down as a prop function (same convention as
// DriverPageDeliveryHistory's `fmtDate`) because it's the exact same helper
// the parent already uses for the reservation-card list and timeline, so it
// stays single-sourced instead of being duplicated here. `waitlistStatusClass`
// / `waitlistStatusLabel` are kept local because they're only ever used in
// this section.
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';

const { t } = useI18n();

defineProps({
  /** Selected waitlist date filter (yyyy-mm-dd); empty string = all dates. */
  date: { type: String, default: '' },
  /** True while the parent is fetching the waitlist. */
  loading: { type: Boolean, default: false },
  /** True when the parent's fetch failed. */
  error: { type: Boolean, default: false },
  /** Waitlist entries for the selected date (or all dates, if date is empty). */
  entries: { type: Array, default: () => [] },
  /** Locale-aware date formatter, owned by the parent (shared with the reservation list). */
  formatDate: { type: Function, required: true },
});

const emit = defineEmits(['update:date', 'refresh']);

const waitlistStatusLabel = (status) => {
  const map = {
    waiting: t("ownerReservations.waitlistStatusWaiting"),
    notified: t("ownerReservations.waitlistStatusNotified"),
    converted: t("ownerReservations.waitlistStatusConverted"),
    expired: t("ownerReservations.waitlistStatusExpired"),
  };
  return map[status] ?? status;
};

const waitlistStatusClass = (status) => {
  if (status === "waiting")   return "bg-amber-500/15 border border-amber-500/30 text-amber-300";
  if (status === "notified")  return "bg-sky-500/15 border border-sky-500/30 text-sky-300";
  if (status === "converted") return "bg-emerald-500/15 border border-emerald-500/30 text-emerald-300";
  if (status === "expired")   return "bg-slate-700/50 border border-slate-600 text-slate-400";
  return "bg-slate-700/50 border border-slate-600 text-slate-400";
};
</script>
