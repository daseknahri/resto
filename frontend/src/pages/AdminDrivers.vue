<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminDrivers.title') }}</h1>
        <p class="text-sm text-slate-400 mt-0.5">{{ t('adminDrivers.subtitle') }}</p>
      </div>
      <button
        class="rounded-full border border-slate-600 px-4 py-2 text-xs font-semibold text-slate-300 hover:border-slate-400"
        @click="fetchDrivers"
      >{{ t('adminDrivers.refresh') }}</button>
    </div>

    <!-- Loading / Error / Empty -->
    <div v-if="loading" class="py-12 text-center text-sm text-slate-400">{{ t('adminDrivers.loading') }}</div>
    <div v-else-if="fetchError" class="py-12 text-center text-sm text-red-300">{{ t('adminDrivers.fetchError') }}</div>
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
            <th class="px-4 py-3 text-left">{{ t('adminDrivers.colName') }}</th>
            <th class="px-4 py-3 text-left">{{ t('adminDrivers.colPhone') }}</th>
            <th class="px-4 py-3 text-center">{{ t('adminDrivers.colStatus') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminDrivers.colJobs') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminDrivers.colCompleted') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminDrivers.colRating') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminDrivers.colSince') }}</th>
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
                rel="noopener"
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
