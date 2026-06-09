<template>
  <div class="ui-page-shell space-y-5">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="ui-kicker">{{ t('adminFlashSales.kicker') }}</p>
          <h1 class="ui-page-title text-xl leading-tight md:text-2xl">{{ t('adminFlashSales.title') }}</h1>
          <p class="mt-0.5 ui-subtle hidden text-xs sm:block">{{ t('adminFlashSales.subtitle') }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="loading"
            :aria-busy="loading"
            @click="fetchSales"
          >
            <svg v-if="loading" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ loading ? t('common.loading') : t('adminFlashSales.refresh') }}
          </button>
        </div>
      </div>
    </header>

    <!-- Create form -->
    <div class="ui-panel p-5 space-y-4">
      <div class="space-y-0.5">
        <p class="ui-kicker">{{ t('adminFlashSales.createKicker') }}</p>
        <h2 class="ui-display text-base font-semibold text-white">{{ t('adminFlashSales.createTitle') }}</h2>
      </div>
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
        <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
        <p class="flex-1 text-sm text-red-300">{{ createError }}</p>
      </div>
      <button
        class="ui-btn-primary ui-press ui-touch-target px-5 py-2 text-sm disabled:opacity-50"
        :disabled="creating"
        @click="createSale"
      >{{ creating ? t('adminFlashSales.creating') : t('adminFlashSales.create') }}</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 3" :key="i" class="ui-skeleton h-20 rounded-2xl" />
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-red-300">{{ t('adminFlashSales.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10 ui-press"
        @click="fetchSales"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!sales.length" class="ui-empty-state p-8 text-center space-y-1">
      <p class="text-sm font-semibold text-slate-100">{{ t('adminFlashSales.empty') }}</p>
    </div>

    <!-- List -->
    <ul v-else class="space-y-3">
      <li
        v-for="(fs, index) in sales"
        :key="fs.id"
        class="ui-panel ui-surface-lift ui-reveal p-4"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0 space-y-1.5">
            <div class="flex flex-wrap items-center gap-2 min-w-0">
              <span class="truncate text-sm font-semibold text-slate-100" :title="fs.name">{{ fs.name }}</span>
              <span class="ui-chip tabular-nums text-[var(--color-secondary)]">−{{ fs.discount_value }}%</span>
              <span v-if="fs.is_live" class="ui-status-pill border-emerald-500/30 bg-emerald-500/10 text-emerald-300">
                <span class="ui-live-dot bg-emerald-400" aria-hidden="true" />
                {{ t('adminFlashSales.live') }}
              </span>
              <span v-else-if="!fs.is_active" class="ui-status-pill text-slate-400">{{ t('adminFlashSales.paused') }}</span>
              <span v-else class="ui-status-pill border-sky-500/30 bg-sky-500/10 text-sky-300">{{ t('adminFlashSales.scheduled') }}</span>
            </div>
            <p v-if="fs.description" class="truncate text-xs text-slate-400" :title="fs.description">{{ fs.description }}</p>
            <p class="text-[11px] tabular-nums text-slate-500">
              {{ fmtDate(fs.active_from) }}<span aria-hidden="true"> → </span><span class="sr-only"> {{ t('adminFlashSales.to') }} </span>{{ fmtDate(fs.active_until) }}
              · {{ t('adminFlashSales.redemptions', { count: fs.redemption_count, max: fs.max_redemptions || '∞' }) }}
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <button
              class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1 px-3 py-1 text-xs font-semibold disabled:opacity-50"
              :class="fs.is_active ? 'text-slate-300 hover:border-amber-400/50 hover:text-amber-300' : 'border-emerald-500/40 text-emerald-300 hover:border-emerald-400/70'"
              :disabled="busyId === fs.id"
              :aria-busy="busyId === fs.id || undefined"
              :aria-label="(fs.is_active ? t('adminFlashSales.pause') : t('adminFlashSales.activate')) + ' ' + fs.name"
              @click="toggleActive(fs)"
            >
              <svg v-if="busyId === fs.id" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
              {{ busyId === fs.id ? t('common.loading') : (fs.is_active ? t('adminFlashSales.pause') : t('adminFlashSales.activate')) }}
            </button>
            <button
              class="ui-btn-outline ui-press ui-touch-target border-red-500/40 px-3 py-1 text-xs text-red-300 hover:border-red-400/60 hover:bg-red-500/10 disabled:opacity-50"
              :disabled="busyId === fs.id"
              :aria-label="t('adminFlashSales.delete') + ' ' + fs.name"
              @click="deleteConfirmId = fs.id"
            >{{ t('adminFlashSales.delete') }}</button>
          </div>
        </div>
        <!-- Inline delete confirm -->
        <Transition name="ui-fade">
          <div
            v-if="deleteConfirmId === fs.id"
            class="mt-3 flex items-center justify-between gap-3 rounded-xl border border-rose-500/20 bg-rose-500/8 px-4 py-2.5"
            role="alert"
          >
            <p class="text-xs text-rose-200">{{ t('adminFlashSales.deleteConfirm', { name: fs.name }) }}</p>
            <div class="flex shrink-0 gap-2">
              <button
                class="inline-flex items-center gap-1 rounded-full border border-rose-500/40 bg-rose-500/20 px-3 py-1 text-[11px] font-semibold text-rose-200 hover:bg-rose-500/30 disabled:opacity-50"
                :disabled="busyId === fs.id"
                :aria-busy="busyId === fs.id || undefined"
                @click="deleteSale(fs)"
              >
                <svg v-if="busyId === fs.id" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3 w-3 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                {{ t('adminFlashSales.deleteYes') }}
              </button>
              <button
                class="rounded-full border border-slate-600/60 px-3 py-1 text-[11px] font-semibold text-slate-400 hover:border-slate-500/60 hover:text-slate-300"
                :disabled="busyId === fs.id"
                @click="deleteConfirmId = null"
              >{{ t('common.back') }}</button>
            </div>
          </div>
        </Transition>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import AppIcon from '../components/AppIcon.vue';

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

const deleteConfirmId = ref(null);
const deleteSale = async (fs) => {
  busyId.value = fs.id;
  try {
    await api.delete(`/admin/flash-sales/${fs.id}/`);
    sales.value = sales.value.filter((s) => s.id !== fs.id);
    deleteConfirmId.value = null;
    toast.show(t('adminFlashSales.deleted'), 'success');
  } catch {
    toast.show(t('adminFlashSales.deleteFailed'), 'error');
    deleteConfirmId.value = null;
  } finally {
    busyId.value = null;
  }
};

onMounted(fetchSales);
</script>
