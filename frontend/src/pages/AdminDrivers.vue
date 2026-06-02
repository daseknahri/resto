<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminDrivers.title') }}</h1>
        <p class="text-sm text-slate-400 mt-0.5">{{ t('adminDrivers.subtitle') }}</p>
      </div>
      <button
        class="rounded-full border border-slate-600 px-4 py-2 text-xs font-semibold text-slate-300 hover:border-slate-400 disabled:opacity-50"
        :disabled="loading"
        @click="fetchDrivers"
      >{{ loading ? '…' : t('adminDrivers.refresh') }}</button>
    </div>

    <!-- Loading: skeleton stats + table -->
    <template v-if="loading">
      <div class="grid grid-cols-3 gap-3">
        <div v-for="i in 3" :key="i" class="animate-pulse rounded-2xl border border-slate-700/60 bg-slate-900 p-4 text-center space-y-2">
          <div class="mx-auto h-7 w-10 rounded bg-slate-700/60" />
          <div class="mx-auto h-2.5 w-20 rounded bg-slate-800/50" />
        </div>
      </div>
      <div class="overflow-x-auto rounded-2xl border border-slate-700/60">
        <table class="w-full text-sm">
          <thead class="bg-slate-800/60 text-xs text-slate-400">
            <tr>
              <th scope="col" class="px-4 py-3 text-left">{{ t('adminDrivers.colName') }}</th>
              <th scope="col" class="px-4 py-3 text-left">{{ t('adminDrivers.colPhone') }}</th>
              <th scope="col" class="px-4 py-3 text-center">{{ t('adminDrivers.colStatus') }}</th>
              <th scope="col" class="px-4 py-3 text-right">{{ t('adminDrivers.colJobs') }}</th>
              <th scope="col" class="px-4 py-3 text-right">{{ t('adminDrivers.colCompleted') }}</th>
              <th scope="col" class="px-4 py-3 text-right">{{ t('adminDrivers.colRating') }}</th>
              <th scope="col" class="px-4 py-3 text-right">{{ t('adminDrivers.colSince') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
            <tr v-for="i in 4" :key="i" class="animate-pulse">
              <td class="px-4 py-3 space-y-1.5"><div class="h-3 w-24 rounded bg-slate-700/60" /><div class="h-2 w-16 rounded bg-slate-800/40" /></td>
              <td class="px-4 py-3"><div class="h-3 w-20 rounded bg-slate-800/60" /></td>
              <td class="px-4 py-3"><div class="mx-auto h-4 w-12 rounded-full bg-slate-800/50" /></td>
              <td class="px-4 py-3"><div class="ml-auto h-3 w-6 rounded bg-slate-800/50" /></td>
              <td class="px-4 py-3"><div class="ml-auto h-3 w-8 rounded bg-slate-800/50" /></td>
              <td class="px-4 py-3"><div class="ml-auto h-3 w-8 rounded bg-slate-800/50" /></td>
              <td class="px-4 py-3"><div class="ml-auto h-3 w-16 rounded bg-slate-800/40" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('adminDrivers.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchDrivers"
      >{{ t('common.retry') }}</button>
    </div>

    <div v-else-if="!drivers.length" class="py-12 text-center text-sm text-slate-400">{{ t('adminDrivers.empty') }}</div>

    <!-- Stats bar -->
    <div v-else class="grid grid-cols-3 gap-3">
      <div class="rounded-2xl border border-slate-700/60 bg-slate-900 p-4 text-center">
        <p class="text-2xl font-bold text-white">{{ drivers.length }}</p>
        <p class="text-xs text-slate-500 mt-0.5">{{ t('adminDrivers.totalDrivers') }}</p>
      </div>
      <div class="rounded-2xl border border-slate-700/60 bg-slate-900 p-4 text-center">
        <p class="text-2xl font-bold text-emerald-400">{{ onlineCount }}</p>
        <p class="text-xs text-slate-500 mt-0.5">{{ t('adminDrivers.online') }}</p>
      </div>
      <div class="rounded-2xl border border-slate-700/60 bg-slate-900 p-4 text-center">
        <p class="text-2xl font-bold text-white">{{ totalDeliveries }}</p>
        <p class="text-xs text-slate-500 mt-0.5">{{ t('adminDrivers.totalDeliveries') }}</p>
      </div>
    </div>

    <!-- Drivers table -->
    <div v-if="drivers.length" class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminDrivers.colName') }}</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminDrivers.colPhone') }}</th>
            <th scope="col" class="px-4 py-3 text-center">{{ t('adminDrivers.colStatus') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminDrivers.colJobs') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminDrivers.colCompleted') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminDrivers.colRating') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminDrivers.colSince') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr
            v-for="d in drivers"
            :key="d.id"
            class="hover:bg-slate-800/30 transition-colors"
          >
            <td class="px-4 py-3 text-slate-200 font-medium">
              {{ d.name || t('adminDrivers.unnamed') }}
              <span v-if="d.email" class="block text-[10px] text-slate-500">{{ d.email }}</span>
            </td>
            <td class="px-4 py-3 text-slate-400">
              <a :href="`tel:${d.phone}`" class="hover:text-sky-400">{{ d.phone }}</a>
            </td>
            <td class="px-4 py-3 text-center">
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="d.is_online
                  ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                  : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
              >
                {{ d.is_online ? t('adminDrivers.statusOnline') : t('adminDrivers.statusOffline') }}
              </span>
              <a
                v-if="d.is_online && d.driver_lat && d.driver_lng"
                :href="`https://www.google.com/maps/search/?api=1&query=${d.driver_lat},${d.driver_lng}`"
                target="_blank"
                rel="noopener noreferrer"
                class="ml-1 text-[10px] text-sky-400 hover:text-sky-300"
              >📍</a>
            </td>
            <td class="px-4 py-3 text-right text-slate-300">{{ d.total_jobs }}</td>
            <td class="px-4 py-3 text-right text-emerald-400">{{ d.completed_jobs }}</td>
            <td class="px-4 py-3 text-right">
              <span v-if="d.avg_rating" class="text-amber-300">★ {{ d.avg_rating }}</span>
              <span v-else class="text-slate-600">—</span>
            </td>
            <td class="px-4 py-3 text-right text-slate-500 text-xs">{{ formatDate(d.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const { t, currentLocale } = useI18n();

const loading = ref(true);
const fetchError = ref(false);
const drivers = ref([]);

const onlineCount = computed(() => drivers.value.filter(d => d.is_online).length);
const totalDeliveries = computed(() => drivers.value.reduce((sum, d) => sum + d.completed_jobs, 0));

const fetchDrivers = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/admin/drivers/');
    drivers.value = res.data;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const formatDate = (iso) => {
  if (!iso) return '—';
  return new Intl.DateTimeFormat(currentLocale.value, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(iso));
};

onMounted(fetchDrivers);
</script>
