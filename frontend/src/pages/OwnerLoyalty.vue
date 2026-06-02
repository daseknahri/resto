<template>
  <div class="space-y-4 pb-6">
    <!-- Page header -->
    <div class="flex items-start justify-between gap-3">
      <div class="space-y-0.5">
        <p class="ui-kicker">{{ t('ownerLoyalty.kicker') }}</p>
        <h1 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ t('ownerLoyalty.title') }}</h1>
        <p class="text-sm text-slate-400">{{ t('ownerLoyalty.subtitle') }}</p>
      </div>
      <svg v-if="updating" aria-hidden="true" class="mt-1 h-4 w-4 shrink-0 animate-spin text-slate-500" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10"/>
      </svg>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="animate-pulse rounded-2xl border border-slate-700/40 bg-slate-900/60 p-4 space-y-4">
      <div class="flex items-center justify-between gap-4">
        <div class="space-y-1.5">
          <div class="h-4 w-32 rounded bg-slate-700/60" />
          <div class="h-3 w-48 rounded bg-slate-800/50" />
        </div>
        <div class="h-6 w-11 rounded-full bg-slate-700/50" />
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <div v-for="i in 4" :key="i" class="space-y-1.5">
          <div class="h-3 w-24 rounded bg-slate-800/60" />
          <div class="h-9 rounded-lg bg-slate-800/50" />
        </div>
      </div>
      <div class="h-9 rounded-xl bg-slate-700/40" />
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('ownerLoyalty.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchConfig"
      >{{ t('ownerLoyalty.retry') }}</button>
    </div>

    <template v-else>
      <!-- Settings card -->
      <div class="ui-panel p-4 space-y-4">
        <!-- Enable / disable toggle -->
        <div class="flex items-center justify-between gap-4">
          <div>
            <p class="text-sm font-semibold text-slate-100">{{ t('ownerLoyalty.enableLabel') }}</p>
            <p class="text-xs text-slate-400 mt-0.5">{{ t('ownerLoyalty.enableHint') }}</p>
          </div>
          <button
            type="button"
            role="switch"
            :aria-checked="form.enabled"
            :aria-label="t('ownerLoyalty.enableLabel')"
            class="relative h-6 w-11 shrink-0 rounded-full border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
            :class="form.enabled
              ? 'border-emerald-500/60 bg-emerald-500/30'
              : 'border-slate-600 bg-slate-800'"
            @click="form.enabled = !form.enabled"
          >
            <span
              class="absolute top-0.5 h-5 w-5 rounded-full transition-transform"
              :class="form.enabled
                ? 'translate-x-5 bg-emerald-400'
                : 'translate-x-0.5 bg-slate-500'"
            />
          </button>
        </div>

        <div class="border-t border-slate-700/50" />

        <!-- Points per unit -->
        <div class="space-y-1.5">
          <label class="block text-xs font-semibold text-slate-300">{{ t('ownerLoyalty.pointsPerUnitLabel') }}</label>
          <div class="flex items-center gap-3">
            <input
              v-model.number="form.points_per_unit"
              type="number"
              min="1"
              step="1"
              class="ui-input w-32"
              :aria-label="t('ownerLoyalty.pointsPerUnitLabel')"
            />
            <span class="text-xs text-slate-400">{{ t('ownerLoyalty.pointsPerUnitSuffix') }}</span>
          </div>
          <p class="text-[11px] text-slate-500">{{ t('ownerLoyalty.pointsPerUnitHint') }}</p>
        </div>

        <!-- Redeem threshold -->
        <div class="space-y-1.5">
          <label class="block text-xs font-semibold text-slate-300">{{ t('ownerLoyalty.redeemThresholdLabel') }}</label>
          <div class="flex items-center gap-3">
            <input
              v-model.number="form.redeem_threshold"
              type="number"
              min="1"
              step="1"
              class="ui-input w-32"
              :aria-label="t('ownerLoyalty.redeemThresholdLabel')"
            />
            <span class="text-xs text-slate-400">{{ t('ownerLoyalty.redeemThresholdSuffix') }}</span>
          </div>
          <p class="text-[11px] text-slate-500">{{ t('ownerLoyalty.redeemThresholdHint') }}</p>
        </div>

        <!-- Points value -->
        <div class="space-y-1.5">
          <label class="block text-xs font-semibold text-slate-300">{{ t('ownerLoyalty.pointsValueLabel') }}</label>
          <div class="flex items-center gap-3">
            <input
              v-model="form.points_value"
              type="number"
              min="0.0001"
              step="0.001"
              class="ui-input w-32"
              :aria-label="t('ownerLoyalty.pointsValueLabel')"
            />
            <span class="text-xs text-slate-400">{{ t('ownerLoyalty.pointsValueSuffix') }}</span>
          </div>
          <p class="text-[11px] text-slate-500">{{ t('ownerLoyalty.pointsValueHint') }}</p>
        </div>

        <!-- Preview card -->
        <div class="rounded-xl border border-indigo-500/25 bg-indigo-500/8 px-4 py-3 space-y-1">
          <p class="text-xs font-semibold text-indigo-300">{{ t('ownerLoyalty.previewTitle') }}</p>
          <p class="text-xs text-slate-400">{{ previewEarn }}</p>
          <p class="text-xs text-slate-400">{{ previewRedeem }}</p>
        </div>

        <div v-if="saveError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
          <p class="flex-1 text-sm text-red-300">{{ saveError }}</p>
        </div>

        <button
          class="ui-btn-primary"
          :disabled="saving"
          @click="save"
        >
          {{ saving ? t('common.saving') : t('common.save') }}
        </button>
      </div>

      <!-- How it works info box -->
      <div class="ui-panel p-4 space-y-3">
        <p class="text-xs font-semibold text-slate-300 uppercase tracking-wider">{{ t('ownerLoyalty.howItWorksTitle') }}</p>
        <ul class="space-y-2 text-xs text-slate-400">
          <li class="flex items-start gap-2"><span class="mt-0.5 shrink-0 text-[var(--color-secondary)]">•</span>{{ t('ownerLoyalty.how1') }}</li>
          <li class="flex items-start gap-2"><span class="mt-0.5 shrink-0 text-[var(--color-secondary)]">•</span>{{ t('ownerLoyalty.how2') }}</li>
          <li class="flex items-start gap-2"><span class="mt-0.5 shrink-0 text-[var(--color-secondary)]">•</span>{{ t('ownerLoyalty.how3') }}</li>
          <li class="flex items-start gap-2"><span class="mt-0.5 shrink-0 text-[var(--color-secondary)]">•</span>{{ t('ownerLoyalty.how4') }}</li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import { isFresh, readCache, writeCache } from '../lib/staleCache';

const { t } = useI18n();
const toast = useToastStore();

const LOYALTY_CACHE_KEY = 'owner.loyalty';
const LOYALTY_TTL_MS = 10 * 60 * 1000; // 10 min — config rarely changes

const loading = ref(false);
const updating = ref(false);
const fetchError = ref(false);
const saving = ref(false);
const saveError = ref('');

const form = reactive({
  enabled: false,
  points_per_unit: 10,
  redeem_threshold: 100,
  points_value: '0.01',
});

const previewEarn = computed(() => {
  const pts = Number(form.points_per_unit) || 0;
  return t('ownerLoyalty.previewEarn', { pts, amount: 1 });
});

const previewRedeem = computed(() => {
  const threshold = Number(form.redeem_threshold) || 0;
  const value = Number(form.points_value) || 0;
  const credit = (threshold * value).toFixed(2);
  return t('ownerLoyalty.previewRedeem', { threshold, credit });
});

const applyConfig = (data) => {
  form.enabled = data.enabled;
  form.points_per_unit = data.points_per_unit;
  form.redeem_threshold = data.redeem_threshold;
  form.points_value = data.points_value;
};

const fetchConfig = async () => {
  const cached = readCache(LOYALTY_CACHE_KEY);
  if (cached) {
    applyConfig(cached);
    if (isFresh(LOYALTY_CACHE_KEY, LOYALTY_TTL_MS)) return;
    updating.value = true;
  } else {
    loading.value = true;
  }
  fetchError.value = false;
  try {
    const res = await api.get('/owner/loyalty/');
    applyConfig(res.data);
    writeCache(LOYALTY_CACHE_KEY, res.data);
  } catch {
    if (!cached) fetchError.value = true;
  } finally {
    loading.value = false;
    updating.value = false;
  }
};

const save = async () => {
  saveError.value = '';
  saving.value = true;
  try {
    const res = await api.patch('/owner/loyalty/', {
      enabled: form.enabled,
      points_per_unit: Number(form.points_per_unit),
      redeem_threshold: Number(form.redeem_threshold),
      points_value: form.points_value,
    });
    applyConfig(res.data);
    writeCache(LOYALTY_CACHE_KEY, res.data); // update cache with saved values
    toast.show(t('ownerLoyalty.saved'), 'success');
  } catch {
    saveError.value = t('ownerLoyalty.saveFailed');
  } finally {
    saving.value = false;
  }
};

onMounted(fetchConfig);
</script>
