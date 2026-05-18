<template>
  <div class="p-6 space-y-6 max-w-lg">
    <div>
      <p class="text-xs text-[var(--color-secondary,#f59e0b)] font-semibold uppercase tracking-widest mb-1">
        {{ t('ownerDelivery.kicker') }}
      </p>
      <h1 class="text-xl font-bold text-white">{{ t('ownerDelivery.title') }}</h1>
      <p class="text-sm text-slate-400 mt-0.5">{{ t('ownerDelivery.subtitle') }}</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-10 text-center text-sm text-slate-400">{{ t('ownerDelivery.loading') }}</div>
    <div v-else-if="fetchError" class="py-10 text-center text-sm text-red-300">{{ t('ownerDelivery.fetchError') }}</div>

    <template v-else>
      <!-- Assigned zone card -->
      <div class="rounded-2xl border border-slate-700/60 bg-slate-900 p-5 space-y-3">
        <h2 class="text-sm font-semibold text-slate-300">{{ t('ownerDelivery.zoneTitle') }}</h2>

        <div v-if="zone" class="space-y-2">
          <div class="flex items-center justify-between gap-2">
            <span class="text-white font-medium">{{ zone.name }}</span>
            <span
              class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
              :class="zone.is_active
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
            >
              {{ zone.is_active ? t('ownerDelivery.zoneActive') : t('ownerDelivery.zoneInactive') }}
            </span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs text-slate-400">
            <div><span class="text-slate-500">{{ t('ownerDelivery.zoneCity') }}</span> {{ zone.city }}</div>
            <div><span class="text-slate-500">{{ t('ownerDelivery.zoneMaxRadius') }}</span> {{ zone.approx_radius_km }} km</div>
          </div>
          <div class="text-xs text-slate-500">{{ t('ownerDelivery.zonePolygon', { n: zone.polygon?.length ?? 0 }) }}</div>
        </div>

        <div v-else class="flex items-start gap-3 rounded-xl border border-slate-700/40 bg-slate-800/50 px-4 py-3">
          <span class="text-xl mt-0.5">🗺</span>
          <div>
            <p class="text-sm text-slate-300 font-medium">{{ t('ownerDelivery.noZoneTitle') }}</p>
            <p class="text-xs text-slate-500 mt-0.5">{{ t('ownerDelivery.noZoneHint') }}</p>
          </div>
        </div>
      </div>

      <!-- Radius setting (only shown when a zone is assigned) -->
      <div v-if="zone" class="rounded-2xl border border-slate-700/60 bg-slate-900 p-5 space-y-4">
        <div>
          <h2 class="text-sm font-semibold text-slate-300">{{ t('ownerDelivery.radiusTitle') }}</h2>
          <p class="text-xs text-slate-500 mt-0.5">{{ t('ownerDelivery.radiusHint', { max: zone.approx_radius_km }) }}</p>
        </div>

        <div class="flex items-end gap-3">
          <div class="flex-1">
            <label class="block text-xs text-slate-400 mb-1">{{ t('ownerDelivery.radiusLabel') }}</label>
            <input
              v-model.number="radiusInput"
              type="number"
              step="0.5"
              min="0.5"
              :max="zone.approx_radius_km"
              class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
              placeholder="5"
            />
          </div>
          <span class="text-sm text-slate-400 mb-2">km</span>
        </div>

        <button
          class="rounded-full bg-[var(--color-secondary,#f59e0b)] px-5 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
          :disabled="saving || !radiusInput"
          @click="saveRadius"
        >
          {{ saving ? '…' : t('ownerDelivery.saveRadius') }}
        </button>
      </div>
    </template>

    <!-- Toast -->
    <Teleport to="body">
      <Transition enter-active-class="transition-all duration-200" enter-from-class="opacity-0 translate-y-2" leave-active-class="transition-all duration-150" leave-to-class="opacity-0 translate-y-2">
        <div
          v-if="toast"
          class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full px-5 py-2.5 text-sm font-medium shadow-xl"
          :class="toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'"
        >
          {{ toast.message }}
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const { t } = useI18n();

const loading = ref(true);
const fetchError = ref(false);
const zone = ref(null);
const radiusInput = ref(null);
const saving = ref(false);
const toast = ref(null);

const showToast = (message, type = 'success') => {
  toast.value = { message, type };
  setTimeout(() => { toast.value = null; }, 3000);
};

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
    showToast(t('ownerDelivery.radiusSaved'));
  } catch {
    showToast(t('ownerDelivery.radiusFailed'), 'error');
  } finally {
    saving.value = false;
  }
};

onMounted(fetchData);
</script>
