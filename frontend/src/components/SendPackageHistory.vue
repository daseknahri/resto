<template>

  <!-- ══════════════════════════ PACKAGE HISTORY ══════════════════════════ -->
  <section v-if="history.length > 0 || loading" class="space-y-2 pt-2">
    <p class="ui-kicker px-1">{{ t('sendPackage.historyTitle') }}</p>

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
        v-for="pkg in history"
        :key="pkg.id"
        class="ui-panel flex items-center gap-3 px-3 py-2.5"
      >
        <!-- Route: dropoff (primary) -->
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm text-slate-200">
            {{ pkg.recipient_name || pkg.dropoff_address || pkg.pickup_address }}
          </p>
          <p class="mt-0.5 truncate text-[11px] text-slate-500">
            {{ fmtDate(pkg.created_at) }}
          </p>
        </div>

        <!-- Fare -->
        <span class="shrink-0 text-sm font-bold tabular-nums text-slate-200">
          {{ formatPrice(pkg.fare) }}
        </span>

        <!-- Status chip -->
        <span
          class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
          :class="pkg.status === 'completed'
            ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
            : 'border border-red-500/30 bg-red-500/10 text-red-300'"
        >
          {{ historyStatusLabel(pkg.status) }}
        </span>

        <!-- Rebook — completed deliveries only -->
        <button
          v-if="pkg.status === 'completed'"
          type="button"
          class="shrink-0 rounded-xl border border-sky-500/30 bg-sky-500/8 px-2.5 py-1.5 text-xs font-semibold text-sky-300 transition hover:bg-sky-500/15 ui-press"
          :aria-label="t('sendPackage.rebookAriaLabel')"
          @click="emit('rebook', pkg)"
        >
          {{ t('sendPackage.rebookCta') }}
        </button>
      </li>
    </ul>
  </section>

  <!-- Empty state — only show after load attempt with no results -->
  <p
    v-else-if="!loading && history.length === 0 && isAuthenticated"
    class="px-1 text-center text-xs text-slate-600"
  >
    {{ t('sendPackage.historyEmpty') }}
  </p>
</template>

<script setup>
// Package-history section of SendPackagePage.vue (the send-package request
// flow), extracted as a standalone presentational component (RISK FE-2).
// Fetch/state ownership stays in the parent: `history` is the parent's
// `packageHistory` computed (its `allHistory` ref, filtered to
// kind === 'package'), and `loading` is the parent's `historyLoading` ref,
// set inside `fetchHistory()`. This component does no fetching and no
// address/fee/geocode logic — it only renders whatever history it's given
// and asks the parent to rebook via the `rebook` emit; the parent's existing
// `rebookPackage(pkg)` (address/coords prefill + scroll-to-form) is
// unchanged.
import { useI18n } from '../composables/useI18n';

const { t, formatPrice, currentLocale } = useI18n();

defineProps({
  /** The customer's package-delivery history (kind === 'package' subset). */
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
    case 'completed': return t('sendPackage.delivered');
    case 'cancelled': return t('sendPackage.cancelled');
    default:          return status;
  }
};
</script>
