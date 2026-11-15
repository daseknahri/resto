<template>
  <div class="ui-page-shell space-y-5">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t('adminRides.kicker') }}</p>
          <h1 class="ui-page-title text-xl md:text-2xl leading-tight">{{ t('adminRides.title') }}</h1>
          <p class="mt-0.5 ui-subtle text-xs hidden sm:block">{{ t('adminRides.subtitle') }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <span v-if="!loading" class="ui-chip tabular-nums">
            {{ total }}
          </span>
          <span class="sr-only" aria-live="polite" aria-atomic="true">{{ loading ? t('common.loading') : '' }}</span>
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="loading || refreshing"
            :aria-busy="loading || refreshing"
            @click="fetchRides({ background: true })"
          >
            <svg v-if="loading || refreshing" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ (loading || refreshing) ? t('common.loading') : t('common.refresh') }}
          </button>
        </div>
      </div>
    </header>

    <!-- Ride fares panel (collapsible) -->
    <section class="ui-panel p-5 space-y-3 ui-reveal" aria-labelledby="ride-fares-title">
      <button
        type="button"
        class="flex w-full items-center justify-between gap-2 text-start"
        :aria-expanded="faresOpen"
        @click="faresOpen = !faresOpen"
      >
        <div>
          <p class="ui-kicker">{{ t('adminRides.faresKicker') }}</p>
          <h2 id="ride-fares-title" class="text-sm font-semibold text-white">{{ t('adminRides.faresTitle') }}</h2>
        </div>
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200"
          :class="faresOpen ? 'rotate-180' : ''"
        ><path d="M4 6l4 4 4-4"/></svg>
      </button>
      <template v-if="faresOpen">
        <p class="text-[11px] text-slate-500">{{ t('adminRides.faresHint') }}</p>
        <div v-if="faresLoadError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ t('adminRides.faresLoadFailed') }}</p>
          <button
            class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10 ui-press"
            @click="fetchFares"
          >{{ t('common.retry') }}</button>
        </div>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <!-- Base fare -->
          <div class="space-y-1">
            <label for="fare-base" class="block text-xs text-slate-400">{{ t('adminRides.baseFare') }}</label>
            <input
              id="fare-base"
              v-model="fares.ride_base_fare"
              type="number"
              step="0.5"
              min="0"
              class="ui-input"
            />
          </div>
          <!-- Per km -->
          <div class="space-y-1">
            <label for="fare-per-km" class="block text-xs text-slate-400">{{ t('adminRides.perKm') }}</label>
            <input
              id="fare-per-km"
              v-model="fares.ride_per_km"
              type="number"
              step="0.5"
              min="0"
              class="ui-input"
            />
          </div>
          <!-- Per minute -->
          <div class="space-y-1">
            <label for="fare-per-min" class="block text-xs text-slate-400">{{ t('adminRides.perMinute') }}</label>
            <input
              id="fare-per-min"
              v-model="fares.ride_per_minute"
              type="number"
              step="0.5"
              min="0"
              class="ui-input"
            />
          </div>
          <!-- Minimum fare -->
          <div class="space-y-1">
            <label for="fare-min" class="block text-xs text-slate-400">{{ t('adminRides.minFare') }}</label>
            <input
              id="fare-min"
              v-model="fares.ride_minimum_fare"
              type="number"
              step="0.5"
              min="0"
              class="ui-input"
            />
          </div>
          <!-- Commission -->
          <div class="space-y-1">
            <label for="fare-commission" class="block text-xs text-slate-400">{{ t('adminRides.commission') }}</label>
            <input
              id="fare-commission"
              v-model="fares.ride_commission_pct"
              type="number"
              step="0.5"
              min="0"
              max="100"
              class="ui-input"
            />
          </div>
        </div>
        <div v-if="faresSaveError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ faresSaveError }}</p>
        </div>
        <button
          class="ui-btn-outline ui-press disabled:opacity-50"
          :disabled="faresSaving"
          @click="saveFares"
        >{{ faresSaving ? t('common.loading') : t('adminRides.faresSave') }}</button>
      </template>
    </section>

    <!-- Status filter chips -->
    <div class="ui-scroll-row min-w-0" role="radiogroup" :aria-label="t('adminRides.filterAll')">
      <button
        v-for="s in STATUSES"
        :key="s"
        role="radio"
        class="ui-state-chip shrink-0 ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
        :data-active="statusFilter === s ? 'true' : 'false'"
        :aria-checked="statusFilter === s"
        @click="setFilter(s)"
      >{{ s === 'all' ? t('adminRides.filterAll') : statusLabel(s) }}</button>
    </div>

    <!-- Background poll failed: keep the last loaded rows, surface a retry (A-07) -->
    <div v-if="refreshFailed && !loading" class="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-amber-300">{{ t('adminRides.refreshFailed') }}</p>
      <button
        class="shrink-0 rounded-lg border border-amber-500/40 px-3 py-1 text-xs font-semibold text-amber-300 hover:bg-amber-500/10 ui-press"
        @click="fetchRides({ background: true })"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="ui-skeleton overflow-hidden">
      <div v-for="i in 6" :key="i" class="flex items-center gap-4 border-b border-slate-800/60 px-4 py-3">
        <div class="h-3 w-24 animate-pulse rounded bg-slate-700/60" />
        <div class="h-3 w-32 animate-pulse rounded bg-slate-700/40 hidden sm:block" />
        <div class="ms-auto h-3 w-16 animate-pulse rounded bg-slate-800/50" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-red-300">{{ t('adminRides.loadFailed') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10 ui-press"
        @click="fetchRides"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!rides.length" class="ui-empty-state text-center p-8 space-y-1">
      <p class="text-sm font-semibold text-slate-100">{{ t('adminRides.empty') }}</p>
    </div>

    <!-- Data views: table (md+) + card list (mobile) -->
    <template v-else>
      <!-- Desktop table (hidden on mobile) -->
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[720px] text-sm">
          <thead class="bg-slate-800/60 text-xs text-slate-400">
            <tr>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminRides.colRide') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminRides.rider') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminRides.driver') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminRides.colRoute') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminRides.colFare') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminRides.colStatus') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminRides.colWhen') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminRides.colActions') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
            <template v-for="(r, index) in rides" :key="r.id">
            <tr
              class="ui-reveal transition-colors hover:bg-slate-800/30"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
            >
              <td class="px-4 py-3 font-mono text-xs text-slate-300">#{{ r.id }}</td>
              <td class="px-4 py-3 text-slate-200 max-w-[120px] truncate" :title="riderLabel(r)">{{ riderLabel(r) }}</td>
              <td class="px-4 py-3 text-slate-400">
                <span v-if="r.driver" class="truncate">{{ r.driver.name || r.driver.phone || ('#' + r.driver.id) }}</span>
                <span v-else class="italic text-slate-600">{{ t('adminRides.unassigned') }}</span>
              </td>
              <td class="px-4 py-3 text-slate-400 max-w-[200px]">
                <span class="block truncate text-xs" :title="r.pickup_address">{{ r.pickup_address || '—' }}</span>
                <span class="block truncate text-xs text-slate-600" :title="r.dropoff_address">&#8594; {{ r.dropoff_address || '—' }}</span>
              </td>
              <td class="px-4 py-3 text-end tabular-nums text-emerald-300">
                {{ fmtMoney(r.fare) }}
                <span class="ms-1 rounded px-1.5 py-0.5 text-[10px] font-semibold" :class="paymentClass(r)">{{ paymentLabel(r) }}</span>
              </td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold" :class="statusClass(r.status)" :aria-label="t('adminRides.colStatus') + ': ' + statusLabel(r.status)">{{ statusLabel(r.status) }}</span>
              </td>
              <td class="px-4 py-3 text-end text-xs text-slate-500 tabular-nums">
                <span class="block">{{ fmtDate(r.created_at) }}</span>
                <span v-if="r.completed_at" class="block text-slate-600">{{ fmtDate(r.completed_at) }}</span>
              </td>
              <td class="px-4 py-3 text-end">
                <button
                  v-if="!isTerminal(r.status)"
                  class="rounded-lg border border-slate-700 px-2.5 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press"
                  @click="openResolve(r)"
                >{{ t('adminRides.resolve') }}</button>
              </td>
            </tr>
            <tr v-if="resolveRideId === r.id">
              <td colspan="8" class="bg-slate-900/60 px-4 py-3">
                <p class="text-sm font-semibold text-slate-100">{{ t('adminRides.resolveTitle', { id: r.id }) }}</p>
                <div class="mt-2 flex flex-wrap items-end gap-2">
                  <label class="space-y-1">
                    <span class="block text-xs text-slate-400">{{ t('adminRides.resolveAction') }}</span>
                    <select v-model="resolveAction" class="ui-input w-auto">
                      <option value="cancel">{{ t('adminRides.resolveCancel') }}</option>
                      <option v-if="r.status === 'in_progress'" value="complete">{{ t('adminRides.resolveComplete') }}</option>
                    </select>
                  </label>
                  <label class="min-w-[220px] flex-1 space-y-1">
                    <span class="block text-xs text-slate-400">{{ t('adminRides.resolveReason') }}</span>
                    <input v-model="resolveReason" type="text" maxlength="300" class="ui-input" />
                  </label>
                  <button
                    class="ui-btn-outline ui-press disabled:opacity-50"
                    :disabled="resolveSaving"
                    @click="confirmResolve(r)"
                  >{{ t('adminRides.resolveConfirm') }}</button>
                  <button
                    class="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press"
                    @click="cancelResolve"
                  >{{ t('common.cancel') }}</button>
                </div>
                <p v-if="resolveError" class="mt-2 text-xs text-red-300" role="alert">{{ resolveError }}</p>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Mobile card list (hidden on md+) -->
      <ul class="md:hidden space-y-2">
        <li
          v-for="(r, index) in rides"
          :key="r.id"
          class="ui-admin-card ui-reveal"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-mono text-xs text-slate-400">#{{ r.id }}</span>
                <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold" :class="statusClass(r.status)">{{ statusLabel(r.status) }}</span>
              </div>
              <p class="mt-0.5 text-sm font-medium text-slate-200 truncate">{{ riderLabel(r) }}</p>
              <p class="mt-0.5 text-xs text-slate-500 truncate">
                <span v-if="r.driver">{{ r.driver.name || r.driver.phone || ('#' + r.driver.id) }}</span>
                <span v-else class="italic text-slate-600">{{ t('adminRides.unassigned') }}</span>
              </p>
              <p class="mt-0.5 text-xs text-slate-600 truncate">{{ r.pickup_address }} &#8594; {{ r.dropoff_address }}</p>
            </div>
            <div class="shrink-0 text-end">
              <p class="font-semibold tabular-nums text-sm text-emerald-300">{{ fmtMoney(r.fare) }}</p>
              <p class="mt-0.5">
                <span class="rounded px-1.5 py-0.5 text-[10px] font-semibold" :class="paymentClass(r)">{{ paymentLabel(r) }}</span>
              </p>
              <p class="mt-0.5 text-[10px] text-slate-600 tabular-nums">{{ fmtDate(r.created_at) }}</p>
            </div>
          </div>
          <button
            v-if="!isTerminal(r.status) && resolveRideId !== r.id"
            class="mt-2 rounded-lg border border-slate-700 px-2.5 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press"
            @click="openResolve(r)"
          >{{ t('adminRides.resolve') }}</button>
          <div v-if="resolveRideId === r.id" class="mt-2 space-y-2 border-t border-slate-800/60 pt-2">
            <p class="text-sm font-semibold text-slate-100">{{ t('adminRides.resolveTitle', { id: r.id }) }}</p>
            <label class="block space-y-1">
              <span class="block text-xs text-slate-400">{{ t('adminRides.resolveAction') }}</span>
              <select v-model="resolveAction" class="ui-input w-full">
                <option value="cancel">{{ t('adminRides.resolveCancel') }}</option>
                <option v-if="r.status === 'in_progress'" value="complete">{{ t('adminRides.resolveComplete') }}</option>
              </select>
            </label>
            <label class="block space-y-1">
              <span class="block text-xs text-slate-400">{{ t('adminRides.resolveReason') }}</span>
              <input v-model="resolveReason" type="text" maxlength="300" class="ui-input" />
            </label>
            <div class="flex gap-2">
              <button
                class="ui-btn-outline ui-press disabled:opacity-50"
                :disabled="resolveSaving"
                @click="confirmResolve(r)"
              >{{ t('adminRides.resolveConfirm') }}</button>
              <button
                class="rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press"
                @click="cancelResolve"
              >{{ t('common.cancel') }}</button>
            </div>
            <p v-if="resolveError" class="text-xs text-red-300" role="alert">{{ resolveError }}</p>
          </div>
        </li>
      </ul>

      <!-- Cap + pagination (A-08): the server total, not rides.length -->
      <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p class="text-xs text-slate-500">{{ t('adminRides.showingLatest', { count: rides.length, total }) }}</p>
        <div v-if="totalPages > 1" class="flex items-center gap-2">
          <button
            class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press disabled:opacity-40"
            :disabled="page <= 1"
            @click="prevPage"
          >{{ t('adminRides.prevPage') }}</button>
          <span class="text-xs text-slate-400 tabular-nums">{{ t('adminRides.pageOf', { page, pages: totalPages }) }}</span>
          <button
            class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press disabled:opacity-40"
            :disabled="page >= totalPages"
            @click="nextPage"
          >{{ t('adminRides.nextPage') }}</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useConfirmModal } from '../composables/useConfirmModal';
import api from '../lib/api';
import adminApi from '../lib/adminApi';
import { formatCurrencyString } from '../lib/intlFormatters';
import AppIcon from '../components/AppIcon.vue';
import { useToastStore } from '../stores/toast';

const { t, currentLocale } = useI18n();
const { confirm } = useConfirmModal();
const toast = useToastStore();

const STATUSES = ['all', 'scheduled', 'searching', 'accepted', 'arrived', 'in_progress', 'completed', 'cancelled'];
const PAGE_SIZE = 50;
const TERMINAL_STATUSES = ['completed', 'cancelled'];
const loading = ref(true);
const refreshing = ref(false);
const fetchError = ref(false);
const refreshFailed = ref(false);
const rides = ref([]);
const total = ref(0);
const page = ref(1);
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));
const statusFilter = ref('all');

// Force-resolve inline panel (A-09)
const resolveRideId = ref(null);
const resolveAction = ref('cancel');
const resolveReason = ref('');
const resolveError = ref('');
const resolveSaving = ref(false);

const isTerminal = (status) => TERMINAL_STATUSES.includes(status);

const STATUS_LABELS = {
  searching: 'adminRides.statusSearching',
  accepted: 'adminRides.statusAccepted',
  arrived: 'adminRides.statusArrived',
  in_progress: 'adminRides.statusInProgress',
  completed: 'adminRides.statusCompleted',
  cancelled: 'adminRides.statusCancelled',
  scheduled: 'tripSchedule.statusScheduled',
};
const statusLabel = (s) => {
  const key = STATUS_LABELS[s];
  if (key) return t(key);
  return t('adminRides.statusUnknown');
};

const statusClass = (s) => {
  if (s === 'completed') return 'bg-emerald-500/12 text-emerald-300';
  if (s === 'cancelled') return 'bg-red-500/12 text-red-300';
  if (s === 'searching') return 'bg-amber-500/12 text-amber-300';
  if (s === 'in_progress') return 'bg-violet-500/12 text-violet-300';
  if (s === 'scheduled') return 'bg-slate-500/12 text-slate-300';
  return 'bg-sky-500/12 text-sky-300';
};

const paymentLabel = (r) => {
  if (r.paid_with_wallet) return t('adminRides.payWallet');
  return t('adminRides.payCash');
};

const paymentClass = (r) => {
  if (r.paid_with_wallet) return 'bg-sky-500/12 text-sky-300';
  return 'bg-amber-500/12 text-amber-300';
};

const riderLabel = (r) => {
  if (!r.rider) return '—';
  return r.rider.name || r.rider.phone || ('#' + r.rider.id);
};

const fmtMoney = (v) =>
  formatCurrencyString(currentLocale.value, v, 'MAD', { maximumFractionDigits: 2 });

const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  } catch {
    return iso.slice(0, 16);
  }
};

const fetchRides = async ({ background = false } = {}) => {
  // A-07: background polls (20s timer, tab-visible) must not flash the skeleton
  // board — they only flip `refreshing`, and a failed poll keeps the last loaded
  // rows with a retry banner instead of swapping in the full error panel.
  if (background) refreshing.value = true;
  else loading.value = true;
  fetchError.value = false;
  try {
    const params = { page: page.value, page_size: PAGE_SIZE };
    if (statusFilter.value !== 'all') params.status = statusFilter.value;
    const res = await api.get('/admin/rides/', { params });
    rides.value = Array.isArray(res.data) ? res.data : (res.data?.results || []);
    // A-08: the envelope total is the count chip + cap note; a bare array has no
    // total, so fall back to the rows actually returned.
    total.value = typeof res.data?.total === 'number' ? res.data.total : rides.value.length;
    refreshFailed.value = false;
  } catch {
    if (background) refreshFailed.value = true;
    else fetchError.value = true;
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
};

const setFilter = (s) => {
  statusFilter.value = s;
  page.value = 1;
  fetchRides();
};

const prevPage = () => {
  if (page.value <= 1) return;
  page.value -= 1;
  fetchRides();
};

const nextPage = () => {
  if (page.value >= totalPages.value) return;
  page.value += 1;
  fetchRides();
};

const openResolve = (ride) => {
  resolveRideId.value = ride.id;
  resolveAction.value = 'cancel';
  resolveReason.value = '';
  resolveError.value = '';
};

const cancelResolve = () => {
  resolveRideId.value = null;
  resolveReason.value = '';
  resolveError.value = '';
};

const confirmResolve = async (ride) => {
  const action = resolveAction.value === 'complete' ? 'complete' : 'cancel';
  const ok = await confirm({
    title: t('adminRides.resolveConfirmTitle', { id: ride.id }),
    body: t('adminRides.resolveConfirmBody'),
    confirmLabel: t('adminRides.resolveConfirm'),
    danger: true,
  });
  if (!ok) return;
  resolveSaving.value = true;
  resolveError.value = '';
  try {
    await api.post(`/admin/rides/${ride.id}/force-resolve/`, {
      action,
      reason: resolveReason.value.trim(),
    });
    ride.status = action === 'complete' ? 'completed' : 'cancelled';
    if (action === 'complete') ride.completed_at = new Date().toISOString();
    cancelResolve();
    toast.show(t('adminRides.resolveDone'), 'success');
  } catch (err) {
    resolveError.value = err?.response?.data?.detail || t('adminRides.resolveFailed');
  } finally {
    resolveSaving.value = false;
  }
};

// ── Ride fares ────────────────────────────────────────────────────────────────
const faresOpen = ref(false);
const FARE_FIELDS = ['ride_base_fare', 'ride_per_km', 'ride_per_minute', 'ride_minimum_fare', 'ride_commission_pct'];
const fares = ref({
  ride_base_fare: '',
  ride_per_km: '',
  ride_per_minute: '',
  ride_minimum_fare: '',
  ride_commission_pct: '',
});
const _faresSnapshot = ref({});
const faresSaving = ref(false);
const faresSaveError = ref('');
const faresLoadError = ref(false);

const fetchFares = async () => {
  // A-10: a failed fares load used to leave the inputs blank (looking "unset").
  // Surface it with a retry, like faresSaveError.
  faresLoadError.value = false;
  try {
    const res = await adminApi.get('/admin/settings/');
    for (const k of FARE_FIELDS) {
      fares.value[k] = res.data?.[k] ?? '';
    }
    _faresSnapshot.value = { ...fares.value };
  } catch {
    faresLoadError.value = true;
  }
};

const saveFares = async () => {
  faresSaveError.value = '';
  // Build partial payload — only send fields that changed
  const changed = {};
  for (const k of FARE_FIELDS) {
    const v = fares.value[k];
    // Number-coerce both sides: the input model yields numbers ("8") while the
    // server snapshot holds decimal strings ("8.00") — string compare would
    // mark every field changed and fire a pointless PATCH.
    if (v !== '' && Number(v) !== Number(_faresSnapshot.value[k])) {
      changed[k] = String(v);
    }
  }
  if (!Object.keys(changed).length) {
    toast.show(t('adminRides.faresNoChanges'), 'info');
    return;
  }
  // A-11: range-check BEFORE the confirm modal — the server enforces the same
  // bounds, but only after the admin has already confirmed (a wasted round-trip
  // and a confusing error). Fares must be >= 0; commission must also be <= 100.
  for (const [k, v] of Object.entries(changed)) {
    const num = Number(v);
    if (!Number.isFinite(num) || num < 0 || (k === 'ride_commission_pct' && num > 100)) {
      faresSaveError.value = t('adminRides.faresRangeInvalid');
      return;
    }
  }
  const okFares = await confirm({
    title: t('adminRides.faresConfirmTitle'),
    body: t('adminRides.faresConfirmBody', { count: Object.keys(changed).length }),
    confirmLabel: t('adminRides.faresSave'),
    danger: true,
  });
  if (!okFares) return;
  faresSaving.value = true;
  try {
    const res = await adminApi.patch('/admin/settings/', changed);
    for (const k of FARE_FIELDS) {
      if (res.data?.[k] !== undefined) fares.value[k] = res.data[k];
    }
    _faresSnapshot.value = { ...fares.value };
    toast.show(t('adminRides.faresSaved'), 'success');
  } catch (err) {
    faresSaveError.value = err?.response?.data?.detail || t('adminRides.faresSaveFailed');
  } finally {
    faresSaving.value = false;
  }
};

// ── Live-ish polling: an ops board left open must not go stale for a whole shift ──
const POLL_MS = 20000;
let pollTimer = null;

const onVisibilityChange = () => {
  if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
    fetchRides({ background: true });
  }
};

onMounted(() => {
  fetchRides();
  fetchFares();
  pollTimer = setInterval(() => fetchRides({ background: true }), POLL_MS);
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange);
  }
});

onUnmounted(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', onVisibilityChange);
  }
});
</script>
