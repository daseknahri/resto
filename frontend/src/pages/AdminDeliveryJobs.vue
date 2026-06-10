<template>
  <div class="ui-page-shell space-y-5">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t('adminDeliveryJobs.kicker') }}</p>
          <h1 class="ui-page-title text-xl md:text-2xl leading-tight">{{ t('adminDeliveryJobs.title') }}</h1>
          <p class="mt-0.5 ui-subtle text-xs hidden sm:block">{{ t('adminDeliveryJobs.subtitle') }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <span v-if="!loading" class="ui-chip tabular-nums">
            {{ t('adminDeliveryJobs.totalLabel', { count: jobs.length }) }}
          </span>
          <span class="sr-only" aria-live="polite" aria-atomic="true">{{ loading ? t('common.loading') : '' }}</span>
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="loading"
            :aria-busy="loading"
            @click="fetchJobs"
          >
            <svg v-if="loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ loading ? t('common.loading') : t('adminDeliveryJobs.refresh') }}
          </button>
        </div>
      </div>
    </header>

    <!-- Status filter chips -->
    <div class="ui-scroll-row min-w-0" role="radiogroup" :aria-label="t('adminDeliveryJobs.filterLabel')">
      <button
        v-for="s in STATUSES"
        :key="s"
        role="radio"
        class="ui-state-chip shrink-0 ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
        :data-active="statusFilter === s ? 'true' : 'false'"
        :aria-checked="statusFilter === s"
        @click="setFilter(s)"
      >{{ s === 'all' ? t('adminDeliveryJobs.all') : statusLabel(s) }}</button>
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
      <p class="flex-1 text-sm text-red-300">{{ t('adminDeliveryJobs.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10 ui-press"
        @click="fetchJobs"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!jobs.length" class="ui-empty-state text-center p-8 space-y-1">
      <p class="text-sm font-semibold text-slate-100">{{ t('adminDeliveryJobs.empty') }}</p>
      <p class="text-xs text-slate-400">{{ t('adminDeliveryJobs.emptyHint') }}</p>
    </div>

    <!-- Data views: table (md+) + card list (mobile) -->
    <template v-else>
      <!-- Desktop table (hidden on mobile) -->
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[680px] text-sm">
          <thead class="bg-slate-800/60 text-xs text-slate-400">
            <tr>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDeliveryJobs.colOrder') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDeliveryJobs.colRestaurant') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDeliveryJobs.colDriver') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDeliveryJobs.colStatus') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDeliveryJobs.colPayout') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDeliveryJobs.colCreated') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
            <tr
              v-for="(j, index) in jobs"
              :key="j.id"
              class="ui-reveal transition-colors hover:bg-slate-800/30"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
            >
              <td class="px-4 py-3 font-mono text-xs text-slate-300">#{{ j.order_number }}</td>
              <td class="px-4 py-3 text-slate-200 max-w-[160px] truncate" :title="j.tenant_name || ('#' + j.tenant_id)">{{ j.tenant_name || ('#' + j.tenant_id) }}</td>
              <td class="px-4 py-3 text-slate-400">
                <span v-if="j.driver" class="truncate">{{ j.driver.name || j.driver.phone || ('#' + j.driver.id) }}</span>
                <span v-else class="italic text-slate-600">{{ t('adminDeliveryJobs.unassigned') }}</span>
              </td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold" :class="statusClass(j.status)" :aria-label="t('adminDeliveryJobs.colStatus') + ': ' + statusLabel(j.status, j.business_type)">{{ statusLabel(j.status, j.business_type) }}</span>
              </td>
              <td class="px-4 py-3 text-end tabular-nums text-emerald-300">{{ fmtMoney(j.driver_payout) }}</td>
              <td class="px-4 py-3 text-end text-xs text-slate-500 tabular-nums">{{ fmtDate(j.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mobile card list (hidden on md+) -->
      <ul class="md:hidden space-y-2">
        <li
          v-for="(j, index) in jobs"
          :key="j.id"
          class="ui-admin-card ui-reveal"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-mono text-xs text-slate-400">#{{ j.order_number }}</span>
                <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold" :class="statusClass(j.status)" :aria-label="t('adminDeliveryJobs.colStatus') + ': ' + statusLabel(j.status, j.business_type)">{{ statusLabel(j.status, j.business_type) }}</span>
              </div>
              <p class="mt-0.5 text-sm font-medium text-slate-200 truncate">{{ j.tenant_name || ('#' + j.tenant_id) }}</p>
              <p class="mt-0.5 text-xs text-slate-500 truncate">
                <span v-if="j.driver">{{ j.driver.name || j.driver.phone || ('#' + j.driver.id) }}</span>
                <span v-else class="italic text-slate-600">{{ t('adminDeliveryJobs.unassigned') }}</span>
              </p>
            </div>
            <div class="shrink-0 text-end">
              <p class="font-semibold tabular-nums text-sm text-emerald-300">{{ fmtMoney(j.driver_payout) }}</p>
              <p class="mt-0.5 text-[10px] text-slate-600 tabular-nums">{{ fmtDate(j.created_at) }}</p>
            </div>
          </div>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import AppIcon from '../components/AppIcon.vue';
import { pickupLabelKey } from '../lib/deliveryVocab';

const { t, currentLocale } = useI18n();

const STATUSES = ['all', 'searching', 'assigned', 'at_restaurant', 'picked_up', 'delivered', 'failed'];
const loading = ref(true);
const fetchError = ref(false);
const jobs = ref([]);
const statusFilter = ref('all');

const STATUS_LABELS = {
  searching: 'adminDeliveryJobs.statusSearching',
  assigned: 'adminDeliveryJobs.statusAssigned',
  at_restaurant: 'adminDeliveryJobs.statusAtRestaurant',
  picked_up: 'adminDeliveryJobs.statusPickedUp',
  delivered: 'adminDeliveryJobs.statusDelivered',
  failed: 'adminDeliveryJobs.statusFailed',
};
// For at_restaurant chips, branch on the job's business_type; all others use static map.
const statusLabel = (s, businessType) => {
  if (s === 'at_restaurant') return t(pickupLabelKey(businessType, 'at'));
  return t(STATUS_LABELS[s] || 'adminDeliveryJobs.statusSearching');
};

const statusClass = (s) => {
  if (s === 'delivered') return 'bg-emerald-500/12 text-emerald-300';
  if (s === 'failed') return 'bg-red-500/12 text-red-300';
  if (s === 'searching') return 'bg-amber-500/12 text-amber-300';
  return 'bg-sky-500/12 text-sky-300';
};

const fmtMoney = (v) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'MAD', maximumFractionDigits: 2 }).format(parseFloat(v || 0));
  } catch {
    return `${parseFloat(v || 0).toFixed(2)}`;
  }
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  } catch {
    return iso.slice(0, 16);
  }
};

const fetchJobs = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const params = {};
    if (statusFilter.value !== 'all') params.status = statusFilter.value;
    const res = await api.get('/admin/delivery-jobs/', { params });
    jobs.value = Array.isArray(res.data) ? res.data : (res.data?.results || []);
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const setFilter = (s) => {
  statusFilter.value = s;
  fetchJobs();
};

onMounted(fetchJobs);
</script>
