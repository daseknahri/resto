<template>
  <div class="owner-page-root">
    <div class="owner-page-header">
      <div>
        <h1 class="owner-page-title">{{ t('ownerLoyalty.title') }}</h1>
        <p class="owner-page-subtitle">{{ t('ownerLoyalty.subtitle') }}</p>
      </div>
    </div>

    <div v-if="loading" class="owner-section-card py-10 text-center text-sm text-slate-400">
      {{ t('common.loading') }}
    </div>

    <template v-else>
      <!-- Enable / disable toggle -->
      <div class="owner-section-card space-y-4">
        <div class="flex items-center justify-between gap-4">
          <div>
            <p class="text-sm font-semibold text-slate-100">{{ t('ownerLoyalty.enableLabel') }}</p>
            <p class="text-xs text-slate-400 mt-0.5">{{ t('ownerLoyalty.enableHint') }}</p>
          </div>
          <!-- Toggle switch -->
          <button
            type="button"
            role="switch"
            :aria-checked="form.enabled"
            class="relative h-6 w-11 shrink-0 rounded-full border transition-colors focus:outline-none"
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

        <!-- Points per unit -->
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('ownerLoyalty.pointsPerUnitLabel') }}</label>
          <div class="flex items-center gap-2">
            <input
              v-model.number="form.points_per_unit"
              type="number"
              min="1"
              step="1"
              class="owner-input w-32"
            />
            <span class="text-xs text-slate-500">{{ t('ownerLoyalty.pointsPerUnitSuffix') }}</span>
          </div>
          <p class="mt-0.5 text-[10px] text-slate-600">{{ t('ownerLoyalty.pointsPerUnitHint') }}</p>
        </div>

        <!-- Redeem threshold -->
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('ownerLoyalty.redeemThresholdLabel') }}</label>
          <div class="flex items-center gap-2">
            <input
              v-model.number="form.redeem_threshold"
              type="number"
              min="1"
              step="1"
              class="owner-input w-32"
            />
            <span class="text-xs text-slate-500">{{ t('ownerLoyalty.redeemThresholdSuffix') }}</span>
          </div>
          <p class="mt-0.5 text-[10px] text-slate-600">{{ t('ownerLoyalty.redeemThresholdHint') }}</p>
        </div>

        <!-- Points value -->
        <div>
          <label class="block text-xs font-medium text-slate-400 mb-1">{{ t('ownerLoyalty.pointsValueLabel') }}</label>
          <div class="flex items-center gap-2">
            <input
              v-model="form.points_value"
              type="number"
              min="0.0001"
              step="0.001"
              class="owner-input w-32"
            />
            <span class="text-xs text-slate-500">{{ t('ownerLoyalty.pointsValueSuffix') }}</span>
          </div>
          <p class="mt-0.5 text-[10px] text-slate-600">{{ t('ownerLoyalty.pointsValueHint') }}</p>
        </div>

        <!-- Preview card -->
        <div class="rounded-xl border border-indigo-500/25 bg-indigo-500/8 p-3 space-y-1">
          <p class="text-xs font-semibold text-indigo-300">{{ t('ownerLoyalty.previewTitle') }}</p>
          <p class="text-xs text-slate-400">{{ previewEarn }}</p>
          <p class="text-xs text-slate-400">{{ previewRedeem }}</p>
        </div>

        <p v-if="saveError" class="text-xs text-red-400">{{ saveError }}</p>

        <button
          class="btn-primary"
          :disabled="saving"
          @click="save"
        >
          {{ saving ? t('common.saving') : t('common.save') }}
        </button>
      </div>

      <!-- How it works info box -->
      <div class="owner-section-card space-y-2 mt-3">
        <p class="text-xs font-semibold text-slate-300 uppercase tracking-wider">{{ t('ownerLoyalty.howItWorksTitle') }}</p>
        <ul class="space-y-1.5 text-xs text-slate-400">
          <li>• {{ t('ownerLoyalty.how1') }}</li>
          <li>• {{ t('ownerLoyalty.how2') }}</li>
          <li>• {{ t('ownerLoyalty.how3') }}</li>
          <li>• {{ t('ownerLoyalty.how4') }}</li>
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
