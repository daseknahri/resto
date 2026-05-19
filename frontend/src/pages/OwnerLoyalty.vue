<template>
  <div class="space-y-4 pb-6">
    <!-- Page header -->
    <div class="space-y-0.5">
      <p class="ui-kicker">{{ t('ownerLoyalty.kicker') }}</p>
      <h1 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ t('ownerLoyalty.title') }}</h1>
      <p class="text-sm text-slate-400">{{ t('ownerLoyalty.subtitle') }}</p>
    </div>

    <div v-if="loading" class="rounded-2xl border border-slate-700/60 bg-slate-900/60 py-10 text-center text-sm text-slate-400">
      {{ t('common.loading') }}
    </div>

    <template v-else>
      <!-- Settings card -->
      <div class="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-5 space-y-5">
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

        <p v-if="saveError" class="text-xs text-red-400">{{ saveError }}</p>

        <button
          class="ui-btn-primary"
          :disabled="saving"
          @click="save"
        >
          {{ saving ? t('common.saving') : t('common.save') }}
        </button>
      </div>

      <!-- How it works info box -->
      <div class="rounded-2xl border border-slate-700/40 bg-slate-900/40 p-5 space-y-3">
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

const { t } = useI18n();
const toast = useToastStore();

const loading = ref(true);
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

const fetchConfig = async () => {
  loading.value = true;
  try {
    const res = await api.get('/owner/loyalty/');
    form.enabled = res.data.enabled;
    form.points_per_unit = res.data.points_per_unit;
    form.redeem_threshold = res.data.redeem_threshold;
    form.points_value = res.data.points_value;
  } catch {
    // silent
  } finally {
    loading.value = false;
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
    form.enabled = res.data.enabled;
    form.points_per_unit = res.data.points_per_unit;
    form.redeem_threshold = res.data.redeem_threshold;
    form.points_value = res.data.points_value;
    toast.show(t('ownerLoyalty.saved'), 'success');
  } catch {
    saveError.value = t('ownerLoyalty.saveFailed');
  } finally {
    saving.value = false;
  }
};

onMounted(fetchConfig);
</script>
