<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminFlashSales.title') }}</h1>
        <p class="mt-0.5 text-sm text-slate-400">{{ t('adminFlashSales.subtitle') }}</p>
      </div>
      <button
        class="rounded-full border border-slate-600 px-4 py-2 text-xs font-semibold text-slate-300 hover:border-slate-400 disabled:opacity-50"
        :disabled="loading"
        @click="fetchSales"
      >{{ loading ? '…' : t('adminFlashSales.refresh') }}</button>
    </div>

    <!-- Create form -->
    <div class="rounded-2xl border border-slate-700/60 bg-slate-800/30 p-5 space-y-4">
      <h2 class="text-sm font-bold text-white">{{ t('adminFlashSales.createTitle') }}</h2>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label class="block text-xs text-slate-400">
          {{ t('adminFlashSales.name') }}
          <input v-model="form.name" type="text" maxlength="100" class="ui-input mt-1 w-full text-sm" :placeholder="t('adminFlashSales.namePlaceholder')" />
        </label>
        <label class="block text-xs text-slate-400">
          {{ t('adminFlashSales.discount') }}
          <input v-model="form.discount_value" type="number" min="1" max="100" step="1" class="ui-input mt-1 w-full text-sm" placeholder="15" />
        </label>
        <label class="block text-xs text-slate-400">
          {{ t('adminFlashSales.activeFrom') }}
          <input v-model="form.active_from" type="datetime-local" class="ui-input mt-1 w-full text-sm" />
        </label>
        <label class="block text-xs text-slate-400">
          {{ t('adminFlashSales.activeUntil') }}
          <input v-model="form.active_until" type="datetime-local" class="ui-input mt-1 w-full text-sm" />
        </label>
        <label class="block text-xs text-slate-400">
          {{ t('adminFlashSales.maxRedemptions') }}
          <input v-model="form.max_redemptions" type="number" min="1" step="1" class="ui-input mt-1 w-full text-sm" :placeholder="t('adminFlashSales.unlimited')" />
        </label>
        <label class="block text-xs text-slate-400 sm:col-span-2">
          {{ t('adminFlashSales.description') }}
          <input v-model="form.description" type="text" maxlength="300" class="ui-input mt-1 w-full text-sm" />
        </label>
      </div>
      <div v-if="createError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <p class="flex-1 text-sm text-red-300">{{ createError }}</p>
      </div>
      <button
        class="rounded-full bg-[var(--color-secondary,#f59e0b)] px-5 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
        :disabled="creating"
        @click="createSale"
      >{{ creating ? t('adminFlashSales.creating') : t('adminFlashSales.create') }}</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 3" :key="i" class="h-20 animate-pulse rounded-2xl bg-slate-800/50" />
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <p class="flex-1 text-sm text-red-300">{{ t('adminFlashSales.fetchError') }}</p>
      <button class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10" @click="fetchSales">{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!sales.length" class="py-10 text-center text-sm text-slate-400">{{ t('adminFlashSales.empty') }}</div>

    <!-- List -->
    <ul v-else class="space-y-3">
      <li v-for="fs in sales" :key="fs.id" class="rounded-2xl border border-slate-700/60 bg-slate-900/50 p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0 space-y-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-slate-100">{{ fs.name }}</span>
              <span class="rounded-full bg-[var(--color-secondary,#f59e0b)]/15 px-2 py-0.5 text-[11px] font-bold text-[var(--color-secondary,#f59e0b)]">−{{ fs.discount_value }}%</span>
              <span v-if="fs.is_live" class="rounded-full bg-emerald-500/12 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">{{ t('adminFlashSales.live') }}</span>
              <span v-else-if="!fs.is_active" class="rounded-full bg-slate-700/60 px-2 py-0.5 text-[10px] font-semibold text-slate-400">{{ t('adminFlashSales.paused') }}</span>
              <span v-else class="rounded-full bg-sky-500/12 px-2 py-0.5 text-[10px] font-semibold text-sky-300">{{ t('adminFlashSales.scheduled') }}</span>
            </div>
            <p v-if="fs.description" class="text-xs text-slate-400">{{ fs.description }}</p>
            <p class="text-[11px] text-slate-500">
              {{ fmtDate(fs.active_from) }} → {{ fmtDate(fs.active_until) }}
              · {{ t('adminFlashSales.redemptions', { count: fs.redemption_count, max: fs.max_redemptions || '∞' }) }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <button
              class="rounded-full border px-3 py-1 text-xs font-semibold transition-colors disabled:opacity-50"
              :class="fs.is_active ? 'border-slate-600 text-slate-300 hover:border-amber-400/50 hover:text-amber-300' : 'border-emerald-500/40 text-emerald-300 hover:border-emerald-400/70'"
              :disabled="busyId === fs.id"
              @click="toggleActive(fs)"
            >{{ fs.is_active ? t('adminFlashSales.pause') : t('adminFlashSales.activate') }}</button>
            <button
              class="rounded-full border border-red-500/40 px-3 py-1 text-xs text-red-300 hover:bg-red-500/10 disabled:opacity-50"
              :disabled="busyId === fs.id"
              @click="deleteSale(fs)"
            >{{ t('adminFlashSales.delete') }}</button>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';

const { t, currentLocale } = useI18n();
const toast = useToastStore();

const loading = ref(true);
const fetchError = ref(false);
const sales = ref([]);
const creating = ref(false);
const createError = ref('');
const busyId = ref(null);

const form = reactive({
  name: '', discount_value: '', active_from: '', active_until: '', max_redemptions: '', description: '',
});

const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  } catch {
    return iso.slice(0, 16);
  }
};

const fetchSales = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/admin/flash-sales/');
    sales.value = Array.isArray(res.data) ? res.data : (res.data?.results || []);
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const createSale = async () => {
  createError.value = '';
  if (!form.name.trim() || !form.discount_value || !form.active_from || !form.active_until) {
    createError.value = t('adminFlashSales.requiredFields');
    return;
  }
  creating.value = true;
  try {
    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      discount_value: Number(form.discount_value),
      active_from: new Date(form.active_from).toISOString(),
      active_until: new Date(form.active_until).toISOString(),
    };
    if (form.max_redemptions) payload.max_redemptions = Number(form.max_redemptions);
    const res = await api.post('/admin/flash-sales/', payload);
    sales.value.unshift(res.data);
    toast.show(t('adminFlashSales.created'), 'success');
    form.name = ''; form.discount_value = ''; form.active_from = ''; form.active_until = '';
    form.max_redemptions = ''; form.description = '';
  } catch (err) {
    createError.value = err?.response?.data?.detail || t('adminFlashSales.createFailed');
  } finally {
    creating.value = false;
  }
};

const toggleActive = async (fs) => {
  busyId.value = fs.id;
  try {
    const res = await api.patch(`/admin/flash-sales/${fs.id}/`, { is_active: !fs.is_active });
    const idx = sales.value.findIndex((s) => s.id === fs.id);
    if (idx >= 0) sales.value[idx] = res.data;
  } catch {
    toast.show(t('adminFlashSales.updateFailed'), 'error');
  } finally {
    busyId.value = null;
  }
};

const deleteSale = async (fs) => {
  if (!window.confirm(t('adminFlashSales.deleteConfirm', { name: fs.name }))) return;
  busyId.value = fs.id;
  try {
    await api.delete(`/admin/flash-sales/${fs.id}/`);
    sales.value = sales.value.filter((s) => s.id !== fs.id);
    toast.show(t('adminFlashSales.deleted'), 'success');
  } catch {
    toast.show(t('adminFlashSales.deleteFailed'), 'error');
  } finally {
    busyId.value = null;
  }
};

onMounted(fetchSales);
</script>
