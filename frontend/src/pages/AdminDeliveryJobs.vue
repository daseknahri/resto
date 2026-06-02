<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminDeliveryJobs.title') }}</h1>
        <p class="mt-0.5 text-sm text-slate-400">{{ t('adminDeliveryJobs.subtitle') }}</p>
      </div>
      <button
        class="rounded-full border border-slate-600 px-4 py-2 text-xs font-semibold text-slate-300 hover:border-slate-400 disabled:opacity-50"
        :disabled="loading"
        @click="fetchJobs"
      >{{ loading ? '…' : t('adminDeliveryJobs.refresh') }}</button>
    </div>

    <!-- Status filter chips -->
    <div class="flex flex-wrap gap-2">
      <button
        v-for="s in STATUSES"
        :key="s"
        class="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors"
        :class="statusFilter === s ? 'border-[var(--color-secondary,#f59e0b)] bg-[var(--color-secondary,#f59e0b)]/10 text-[var(--color-secondary,#f59e0b)]' : 'border-slate-700 text-slate-400 hover:border-slate-500'"
        @click="setFilter(s)"
      >{{ s === 'all' ? t('adminDeliveryJobs.all') : statusLabel(s) }}</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="overflow-hidden rounded-2xl border border-slate-700/60">
      <div v-for="i in 6" :key="i" class="flex items-center gap-4 border-b border-slate-800/60 px-4 py-3">
        <div class="h-3 w-24 animate-pulse rounded bg-slate-700/60" />
        <div class="ml-auto h-3 w-16 animate-pulse rounded bg-slate-800/50" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <p class="flex-1 text-sm text-red-300">{{ t('adminDeliveryJobs.fetchError') }}</p>
      <button class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10" @click="fetchJobs">{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!jobs.length" class="py-10 text-center text-sm text-slate-400">{{ t('adminDeliveryJobs.empty') }}</div>

    <!-- Table -->
    <div v-else class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminDeliveryJobs.colOrder') }}</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminDeliveryJobs.colRestaurant') }}</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminDeliveryJobs.colDriver') }}</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminDeliveryJobs.colStatus') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminDeliveryJobs.colPayout') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminDeliveryJobs.colCreated') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="j in jobs" :key="j.id" class="hover:bg-slate-800/30 transition-colors">
            <td class="px-4 py-3 font-mono text-xs text-slate-300">#{{ j.order_number }}</td>
            <td class="px-4 py-3 text-slate-200">{{ j.tenant_name || ('#' + j.tenant_id) }}</td>
            <td class="px-4 py-3 text-slate-400">
              <span v-if="j.driver">{{ j.driver.name || j.driver.phone || ('#' + j.driver.id) }}</span>
              <span v-else class="text-slate-600 italic">{{ t('adminDeliveryJobs.unassigned') }}</span>
            </td>
            <td class="px-4 py-3">
              <span class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold" :class="statusClass(j.status)">{{ statusLabel(j.status) }}</span>
            </td>
            <td class="px-4 py-3 text-right tabular-nums text-emerald-300">{{ fmtMoney(j.driver_payout) }}</td>
            <td class="px-4 py-3 text-right text-xs text-slate-500">{{ fmtDate(j.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

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
const statusLabel = (s) => t(STATUS_LABELS[s] || 'adminDeliveryJobs.statusSearching');

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
