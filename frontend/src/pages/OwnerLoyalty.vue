<template>
  <div class="ui-page-shell space-y-4 pb-6">
    <!-- Page header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0 space-y-0.5">
          <p class="ui-kicker">{{ t('ownerLoyalty.kicker') }}</p>
          <h1 class="ui-display text-xl font-bold tracking-tight text-white leading-tight sm:text-2xl">
            {{ t('ownerLoyalty.title') }}
          </h1>
          <p class="ui-subtle mt-0.5 text-xs">{{ t('ownerLoyalty.subtitle') }}</p>
        </div>
        <div class="mt-1 shrink-0">
          <svg
            v-if="updating"
            aria-hidden="true"
            class="h-4 w-4 animate-spin text-slate-500"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10" />
          </svg>
          <span class="sr-only" aria-live="polite" aria-atomic="true">{{ updating ? t('common.updating') : '' }}</span>
        </div>
      </div>
    </header>

    <!-- Loading skeleton -->
    <div v-if="loading" class="ui-panel animate-pulse p-4 space-y-4" aria-busy="true">
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
    <div
      v-else-if="fetchError"
      class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3"
      role="alert"
    >
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path
          fill-rule="evenodd"
          d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z"
          clip-rule="evenodd"
        />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('ownerLoyalty.fetchError') }}</p>
      <button
        class="ui-press shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/60"
        @click="fetchConfig"
      >
        {{ t('ownerLoyalty.retry') }}
      </button>
    </div>

    <template v-else>
      <!-- Enrollment stats — only shown if at least one customer has earned points -->
      <section
        v-if="stats"
        class="ui-panel ui-reveal p-4"
        :style="{ '--ui-delay': '14ms' }"
      >
        <p class="ui-kicker mb-3 tracking-wide">{{ t('ownerLoyalty.statsKicker') }}</p>
        <div v-if="stats.enrolled_customers === 0" class="flex items-center gap-2 text-xs text-slate-500">
          <svg aria-hidden="true" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0 text-slate-600"><path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1ZM7.25 5a.75.75 0 0 1 1.5 0v3a.75.75 0 0 1-1.5 0V5Zm.75 7a1 1 0 1 1 0-2 1 1 0 0 1 0 2Z"/></svg>
          {{ t('ownerLoyalty.statsNoEnrollments') }}
        </div>
        <div v-else class="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-800 bg-slate-800">
          <div class="bg-slate-950/70 px-4 py-3 text-center">
            <p class="text-xl font-bold tabular-nums text-white leading-none">{{ stats.enrolled_customers }}</p>
            <p class="ui-stat-label mt-1.5 text-[10px]">{{ t('ownerLoyalty.statsEnrolled') }}</p>
          </div>
          <div class="bg-slate-950/70 px-4 py-3 text-center">
            <p class="text-xl font-bold tabular-nums text-[var(--color-secondary)] leading-none">{{ stats.total_points_issued.toLocaleString() }}</p>
            <p class="ui-stat-label mt-1.5 text-[10px]">{{ t('ownerLoyalty.statsTotalPoints') }}</p>
          </div>
        </div>
      </section>

      <!-- How it works — shown first so owners understand the model before configuring -->
      <section class="ui-panel ui-reveal p-4 space-y-3" :style="{ '--ui-delay': '28ms' }">
        <h2 class="ui-kicker tracking-wide">{{ t('ownerLoyalty.howItWorksTitle') }}</h2>
        <ul class="space-y-2.5">
          <li class="flex items-start gap-2.5 text-xs text-slate-400 leading-relaxed">
            <span class="mt-0.5 shrink-0 text-[var(--color-secondary)] text-sm" aria-hidden="true">•</span>
            {{ t('ownerLoyalty.how1') }}
          </li>
          <li class="flex items-start gap-2.5 text-xs text-slate-400 leading-relaxed">
            <span class="mt-0.5 shrink-0 text-[var(--color-secondary)] text-sm" aria-hidden="true">•</span>
            {{ t('ownerLoyalty.how2') }}
          </li>
          <li class="flex items-start gap-2.5 text-xs text-slate-400 leading-relaxed">
            <span class="mt-0.5 shrink-0 text-[var(--color-secondary)] text-sm" aria-hidden="true">•</span>
            {{ t('ownerLoyalty.how3') }}
          </li>
          <li class="flex items-start gap-2.5 text-xs text-slate-400 leading-relaxed">
            <span class="mt-0.5 shrink-0 text-[var(--color-secondary)] text-sm" aria-hidden="true">•</span>
            {{ t('ownerLoyalty.how4') }}
          </li>
        </ul>
      </section>

      <!-- Settings card -->
      <section class="ui-panel ui-reveal p-4 space-y-5" :style="{ '--ui-delay': '56ms' }">
        <!-- Section heading -->
        <div class="space-y-0.5">
          <p class="ui-kicker tracking-wide">{{ t('ownerLoyalty.settingsKicker') }}</p>
          <h2 class="text-sm font-semibold text-slate-100 leading-snug">{{ t('ownerLoyalty.settingsTitle') }}</h2>
        </div>

        <!-- Enable / disable toggle -->
        <div class="flex items-center justify-between gap-4 rounded-xl border border-slate-700/50 bg-slate-800/30 px-4 py-3">
          <div class="min-w-0">
            <p class="text-sm font-semibold text-slate-100">{{ t('ownerLoyalty.enableLabel') }}</p>
            <p class="mt-0.5 text-xs text-slate-400">{{ t('ownerLoyalty.enableHint') }}</p>
          </div>
          <button
            type="button"
            role="switch"
            :aria-checked="form.enabled"
            :aria-label="t('ownerLoyalty.enableLabel')"
            class="ui-touch-target relative h-6 w-11 shrink-0 rounded-full border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
            :class="
              form.enabled ? 'border-emerald-500/60 bg-emerald-500/30' : 'border-slate-600 bg-slate-800'
            "
            @click="form.enabled = !form.enabled"
          >
            <span
              class="absolute top-0.5 h-5 w-5 rounded-full transition-transform"
              :class="form.enabled ? 'translate-x-5 bg-emerald-400' : 'translate-x-0.5 bg-slate-500'"
            />
          </button>
        </div>

        <div class="border-t border-slate-700/40" />

        <!-- Earn / redemption fields -->
        <div class="space-y-4">

          <!-- Points per unit -->
          <div class="space-y-1.5">
            <label for="loyalty-points-per-unit" class="block text-xs font-semibold text-slate-300">
              {{ t('ownerLoyalty.pointsPerUnitLabel') }}
            </label>
            <div class="flex flex-wrap items-center gap-3">
              <input
                id="loyalty-points-per-unit"
                v-model.number="form.points_per_unit"
                type="number"
                min="1"
                step="1"
                class="ui-input w-32 tabular-nums"
              />
              <span class="text-xs text-slate-400">{{ t('ownerLoyalty.pointsPerUnitSuffix') }}</span>
            </div>
            <p class="text-[11px] leading-relaxed text-slate-500">{{ t('ownerLoyalty.pointsPerUnitHint') }}</p>
          </div>

          <!-- Redeem threshold -->
          <div class="space-y-1.5">
            <label for="loyalty-redeem-threshold" class="block text-xs font-semibold text-slate-300">
              {{ t('ownerLoyalty.redeemThresholdLabel') }}
            </label>
            <div class="flex flex-wrap items-center gap-3">
              <input
                id="loyalty-redeem-threshold"
                v-model.number="form.redeem_threshold"
                type="number"
                min="1"
                step="1"
                class="ui-input w-32 tabular-nums"
              />
              <span class="text-xs text-slate-400">{{ t('ownerLoyalty.redeemThresholdSuffix') }}</span>
            </div>
            <p class="text-[11px] leading-relaxed text-slate-500">{{ t('ownerLoyalty.redeemThresholdHint') }}</p>
          </div>

          <!-- Points value -->
          <div class="space-y-1.5">
            <label for="loyalty-points-value" class="block text-xs font-semibold text-slate-300">
              {{ t('ownerLoyalty.pointsValueLabel') }}
            </label>
            <div class="flex flex-wrap items-center gap-3">
              <input
                id="loyalty-points-value"
                v-model="form.points_value"
                type="number"
                min="0.0001"
                step="0.001"
                class="ui-input w-32 tabular-nums"
              />
              <span class="text-xs text-slate-400">{{ t('ownerLoyalty.pointsValueSuffix') }}</span>
            </div>
            <p class="text-[11px] leading-relaxed text-slate-500">{{ t('ownerLoyalty.pointsValueHint') }}</p>
          </div>
        </div>

        <!-- Preview card -->
        <div
          class="ui-section-band space-y-2 rounded-xl px-4 py-3.5"
          role="group"
          aria-labelledby="loyalty-preview-label"
        >
          <p id="loyalty-preview-label" class="ui-kicker text-[var(--color-secondary)] tracking-wide">{{ t('ownerLoyalty.previewTitle') }}</p>
          <p class="text-xs tabular-nums text-slate-300 leading-relaxed">{{ previewEarn }}</p>
          <p class="text-xs tabular-nums text-slate-300 leading-relaxed">{{ previewRedeem }}</p>
        </div>

        <div
          v-if="saveError"
          class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
          role="alert"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            class="mt-0.5 h-4 w-4 shrink-0 text-red-400"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
              clip-rule="evenodd"
            />
          </svg>
          <p class="flex-1 text-sm text-red-300">{{ saveError }}</p>
        </div>

        <button class="ui-btn-primary ui-press w-full" :disabled="saving" :aria-busy="saving" @click="save">
          {{ saving ? t('common.saving') : t('common.save') }}
        </button>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onActivated, onMounted, reactive, ref } from 'vue';
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
const stats = ref(null);

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
  if (data.stats) stats.value = data.stats;
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
  // Client-side guard: prevent sending zeroes the backend would reject
  if (form.enabled) {
    const ppu = Number(form.points_per_unit);
    const thr = Number(form.redeem_threshold);
    const val = Number(form.points_value);
    if (!ppu || ppu < 1) { saveError.value = t('ownerLoyalty.validationPPU'); return; }
    if (!thr || thr < 1) { saveError.value = t('ownerLoyalty.validationThreshold'); return; }
    if (!val || val <= 0) { saveError.value = t('ownerLoyalty.validationValue'); return; }
  }
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

// Kept alive — silently revalidate on revisit (cached view shows instantly).
let _activatedOnce = false;
onActivated(() => {
  if (!_activatedOnce) { _activatedOnce = true; return; }
  fetchConfig();
});
</script>
