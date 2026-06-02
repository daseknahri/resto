<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminCustomers.title') }}</h1>
        <p class="mt-0.5 text-sm text-slate-400">{{ t('adminCustomers.subtitle') }}</p>
      </div>
      <span v-if="!loading" class="shrink-0 rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1 text-xs text-slate-300">
        {{ t('adminCustomers.totalLabel', { count: total }) }}
      </span>
    </div>

    <!-- Search + filters -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative flex-1 min-w-[200px]">
        <AppIcon name="search" class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          v-model="search"
          type="text"
          class="w-full rounded-xl border border-slate-700 bg-slate-800 py-2.5 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
          :aria-label="t('adminCustomers.searchPlaceholder')"
          :placeholder="t('adminCustomers.searchPlaceholder')"
          @input="onSearch"
        />
      </div>
      <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
        <input v-model="verifiedOnly" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" @change="reload" />
        {{ t('adminCustomers.filterVerified') }}
      </label>
      <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
        <input v-model="driversOnly" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" @change="reload" />
        {{ t('adminCustomers.filterDrivers') }}
      </label>
      <button
        class="rounded-xl border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-sm text-slate-300 hover:border-slate-500 disabled:opacity-50 transition-colors"
        :disabled="loading"
        @click="reload"
      >{{ loading ? '…' : t('adminCustomers.refresh') }}</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="overflow-hidden rounded-2xl border border-slate-700/60">
      <div v-for="i in 6" :key="i" class="flex items-center gap-4 border-b border-slate-800/60 px-4 py-3">
        <div class="h-3 w-32 animate-pulse rounded bg-slate-700/60" />
        <div class="ml-auto h-3 w-16 animate-pulse rounded bg-slate-800/50" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <p class="flex-1 text-sm text-red-300">{{ t('adminCustomers.fetchError') }}</p>
      <button class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10" @click="reload">
        {{ t('common.retry') }}
      </button>
    </div>

    <!-- Empty -->
    <div v-else-if="!customers.length" class="py-10 text-center text-sm text-slate-400">{{ t('adminCustomers.empty') }}</div>

    <!-- Table -->
    <div v-else class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminCustomers.colCustomer') }}</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminCustomers.colContact') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminCustomers.colWallet') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminCustomers.colLoyalty') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminCustomers.colJoined') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="c in customers" :key="c.id" class="hover:bg-slate-800/30 transition-colors">
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span class="font-medium text-slate-200">{{ c.name || t('adminCustomers.unnamed') }}</span>
                <span v-if="c.is_driver" class="rounded-full bg-emerald-500/12 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">{{ t('adminCustomers.driver') }}</span>
              </div>
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-col gap-0.5">
                <span class="flex items-center gap-1.5 text-slate-300">
                  {{ c.phone || '—' }}
                  <span v-if="c.phone && c.phone_verified" class="text-[10px] text-emerald-400">✓</span>
                </span>
                <span v-if="c.email" class="text-xs text-slate-500">{{ c.email }}</span>
              </div>
            </td>
            <td class="px-4 py-3 text-right">
              <span class="font-semibold tabular-nums" :class="parseFloat(c.wallet_balance) > 0 ? 'text-emerald-400' : 'text-slate-500'">
                {{ fmtMoney(c.wallet_balance) }}
              </span>
            </td>
            <td class="px-4 py-3 text-right tabular-nums text-slate-300">{{ c.loyalty_points }}</td>
            <td class="px-4 py-3 text-right text-xs text-slate-500">{{ fmtDate(c.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="!loading && total > pageSize" class="flex items-center justify-between text-xs text-slate-400">
      <span>{{ t('adminCustomers.showing', { from: (page - 1) * pageSize + 1, to: Math.min(page * pageSize, total), total }) }}</span>
      <div class="flex gap-2">
        <button class="rounded-lg border border-slate-700 px-3 py-1.5 hover:border-slate-500 disabled:opacity-40" :disabled="page <= 1" @click="changePage(page - 1)">← {{ t('adminCustomers.prev') }}</button>
        <button class="rounded-lg border border-slate-700 px-3 py-1.5 hover:border-slate-500 disabled:opacity-40" :disabled="page * pageSize >= total" @click="changePage(page + 1)">{{ t('adminCustomers.next') }} →</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const { t, currentLocale } = useI18n();

const loading = ref(true);
const fetchError = ref(false);
const customers = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 25;
const search = ref('');
const verifiedOnly = ref(false);
const driversOnly = ref(false);
let searchTimer = null;

const fmtMoney = (v) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'MAD', maximumFractionDigits: 2 })
      .format(parseFloat(v || 0));
  } catch {
    return `${parseFloat(v || 0).toFixed(2)}`;
  }
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: 'medium' }).format(new Date(iso));
  } catch {
    return iso.slice(0, 10);
  }
};

const fetchCustomers = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const params = { page: page.value, page_size: pageSize };
    if (search.value.trim()) params.search = search.value.trim();
    if (verifiedOnly.value) params.verified_only = 1;
    if (driversOnly.value) params.drivers_only = 1;
    const res = await api.get('/admin/customers/', { params });
    customers.value = res.data?.results || [];
    total.value = res.data?.total || 0;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const reload = () => {
  page.value = 1;
  fetchCustomers();
};

const onSearch = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(reload, 400);
};

const changePage = (p) => {
  page.value = p;
  fetchCustomers();
};

onMounted(fetchCustomers);
</script>
