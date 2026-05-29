<template>
  <div class="space-y-4 pb-6">
    <!-- Page header -->
    <div class="space-y-0.5">
      <p class="ui-kicker">{{ t('ownerDelivery.kicker') }}</p>
      <h1 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ t('ownerDelivery.title') }}</h1>
      <p class="text-sm text-slate-400">{{ t('ownerDelivery.subtitle') }}</p>
    </div>

    <!-- Loading: skeleton -->
    <div v-if="loading" class="space-y-4">
      <!-- Zone card skeleton -->
      <div class="animate-pulse rounded-2xl border border-slate-700/40 bg-slate-900/60 p-5 space-y-3">
        <div class="h-3.5 w-24 rounded bg-slate-700/60" />
        <div class="flex items-center justify-between">
          <div class="h-4 w-32 rounded bg-slate-700/60" />
          <div class="h-5 w-16 rounded-full bg-slate-800/60" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div class="h-8 rounded-lg bg-slate-800/50" />
          <div class="h-8 rounded-lg bg-slate-800/50" />
        </div>
      </div>
      <!-- Settings card skeleton -->
      <div class="animate-pulse rounded-2xl border border-slate-700/40 bg-slate-900/60 p-5 space-y-4">
        <div class="h-3.5 w-28 rounded bg-slate-700/60" />
        <div class="grid gap-3 sm:grid-cols-2">
          <div v-for="i in 4" :key="i" class="space-y-1.5">
            <div class="h-3 w-20 rounded bg-slate-800/60" />
            <div class="h-9 rounded-lg bg-slate-800/50" />
          </div>
        </div>
        <div class="h-9 w-32 rounded-xl bg-slate-700/40" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
      <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('ownerDelivery.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchData"
      >{{ t('common.retry') }}</button>
    </div>

    <template v-else>
      <!-- Assigned zone card -->
      <div class="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-5 space-y-4">
        <h2 class="text-sm font-semibold text-slate-300">{{ t('ownerDelivery.zoneTitle') }}</h2>

        <div v-if="zone" class="space-y-3">
          <div class="flex items-center justify-between gap-2">
            <span class="font-medium text-white">{{ zone.name }}</span>
            <span
              class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold"
              :class="zone.is_active
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
            >
              {{ zone.is_active ? t('ownerDelivery.zoneActive') : t('ownerDelivery.zoneInactive') }}
            </span>
          </div>
          <div class="grid grid-cols-2 gap-3 text-xs text-slate-400">
            <div>
              <span class="block text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">{{ t('ownerDelivery.zoneCity') }}</span>
              {{ zone.city }}
            </div>
            <div>
              <span class="block text-[10px] uppercase tracking-wider text-slate-500 mb-0.5">{{ t('ownerDelivery.zoneMaxRadius') }}</span>
              {{ zone.approx_radius_km }} km
            </div>
          </div>
          <p class="text-xs text-slate-500">{{ t('ownerDelivery.zonePolygon', { n: zone.polygon?.length ?? 0 }) }}</p>
        </div>

        <div v-else class="flex items-start gap-3 rounded-xl border border-slate-700/40 bg-slate-800/40 px-4 py-3">
          <span class="text-xl mt-0.5">🗺</span>
          <div>
            <p class="text-sm font-medium text-slate-300">{{ t('ownerDelivery.noZoneTitle') }}</p>
            <p class="text-xs text-slate-500 mt-0.5">{{ t('ownerDelivery.noZoneHint') }}</p>
          </div>
        </div>
      </div>

      <!-- Radius setting (only shown when a zone is assigned) -->
      <div v-if="zone" class="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-5 space-y-4">
        <div>
          <h2 class="text-sm font-semibold text-slate-300">{{ t('ownerDelivery.radiusTitle') }}</h2>
          <p class="text-xs text-slate-500 mt-0.5">{{ t('ownerDelivery.radiusHint', { max: zone.approx_radius_km }) }}</p>
        </div>

        <div class="flex items-end gap-3">
          <div class="flex-1 max-w-[10rem]">
            <label class="block text-xs font-semibold text-slate-300 mb-1.5">{{ t('ownerDelivery.radiusLabel') }}</label>
            <input
              v-model.number="radiusInput"
              type="number"
              step="0.5"
              min="0.5"
              :max="zone.approx_radius_km"
              class="ui-input w-full"
              placeholder="5"
            />
          </div>
          <span class="text-sm text-slate-400 mb-2.5">km</span>
        </div>

        <button
          class="ui-btn-primary"
          :disabled="saving || !radiusInput"
          @click="saveRadius"
        >
          {{ saving ? t('common.saving') : t('ownerDelivery.saveRadius') }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';

const { t } = useI18n();
const toast = useToastStore();

const loading = ref(true);
const fetchError = ref(false);
const zone = ref(null);
const radiusInput = ref(null);
const saving = ref(false);

const fetchData = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/owner/delivery-zone/');
    zone.value = res.data.zone;
    radiusInput.value = res.data.delivery_radius_km ?? (res.data.zone?.approx_radius_km ?? 5);
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const saveRadius = async () => {
  if (!radiusInput.value || saving.value) return;
  saving.value = true;
  try {
    await api.patch('/owner/delivery-radius/', { delivery_radius_km: radiusInput.value });
    toast.show(t('ownerDelivery.radiusSaved'), 'success');
  } catch {
    toast.show(t('ownerDelivery.radiusFailed'), 'error');
  } finally {
    saving.value = false;
  }
};

onMounted(fetchData);
</script>
