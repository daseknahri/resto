<template>
  <div class="ui-panel p-3" :aria-busy="loading || updating">
    <!-- Header with toggle -->
    <div class="mb-3 flex flex-wrap items-center justify-between gap-x-2 gap-y-1.5">
      <div class="min-w-0">
        <p class="ui-kicker inline-flex items-center gap-1.5">
          {{ t('bestSellers.title') }}
          <svg
            v-if="updating"
            aria-hidden="true"
            class="h-3 w-3 animate-spin text-slate-600"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10" />
          </svg>
        </p>
        <span class="sr-only" aria-live="polite">{{ loading ? t('common.loading') : updating ? t('bestSellers.updating') : '' }}</span>
        <h2 class="text-sm font-semibold text-slate-50">{{ t('bestSellers.heading') }}</h2>
      </div>
      <div role="radiogroup" class="ui-segmented shrink-0 max-w-fit p-0.5" :aria-label="t('bestSellers.modeNav')">
        <button
          class="ui-segmented-button px-2.5 py-1 text-[11px]"
          role="radio"
          :data-active="mode === 'count'"
          :aria-checked="mode === 'count'"
          @click="mode = 'count'"
        >{{ t('bestSellers.byOrders') }}</button>
        <button
          class="ui-segmented-button px-2.5 py-1 text-[11px]"
          role="radio"
          :data-active="mode === 'revenue'"
          :aria-checked="mode === 'revenue'"
          @click="mode = 'revenue'"
        >{{ t('bestSellers.byRevenue') }}</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="ui-skeleton px-3 py-2.5">
      <div class="space-y-2.5">
        <div v-for="i in 5" :key="i" class="flex items-center gap-2.5">
          <div class="h-3 w-3 shrink-0 animate-pulse rounded bg-slate-700/60" />
          <div class="min-w-0 flex-1 space-y-1">
            <div class="flex justify-between gap-2">
              <div class="h-2.5 w-24 animate-pulse rounded bg-slate-700/60" :style="{ animationDelay: `${i * 60}ms` }" />
              <div class="h-2.5 w-10 animate-pulse rounded bg-slate-700/40" :style="{ animationDelay: `${i * 60 + 30}ms` }" />
            </div>
            <div class="h-1 animate-pulse rounded-full bg-slate-700/40" :style="{ animationDelay: `${i * 60 + 60}ms` }" />
          </div>
        </div>
      </div>
    </div>

    <!-- Rows -->
    <ol v-else-if="rows.length" class="space-y-1.5">
      <li
        v-for="(dish, idx) in rows"
        :key="dish.dish_slug"
        class="ui-reveal flex items-center gap-2.5"
        :style="{ '--ui-delay': `${Math.min(idx, 9) * 28}ms` }"
      >
        <!-- Rank -->
        <span
          class="w-4 shrink-0 text-center text-[10px] font-bold tabular-nums"
          :class="idx === 0 ? 'text-[var(--color-secondary)]' : idx === 1 ? 'text-slate-300' : idx === 2 ? 'text-amber-600/70' : 'text-slate-400'"
        >{{ idx + 1 }}</span>

        <!-- Bar + label -->
        <div class="min-w-0 flex-1">
          <div class="mb-0.5 flex items-center justify-between gap-1">
            <span class="truncate text-xs font-medium text-slate-200">{{ dish.dish_name }}</span>
            <span class="shrink-0 text-[10px] tabular-nums text-slate-400">
              {{ mode === 'count' ? t('bestSellers.qty', { n: dish.total_qty }) : fmtMoney(dish.revenue) }}
            </span>
          </div>
          <div
            class="h-1 overflow-hidden rounded-full bg-slate-800/70"
            role="progressbar"
            :aria-valuenow="barPct(dish)"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-label="`${dish.dish_name} — ${mode === 'count' ? t('bestSellers.qty', { n: dish.total_qty }) : fmtMoney(dish.revenue)} (${barPct(dish)}%)`"
          >
            <div
              class="h-full rounded-full bg-[var(--color-secondary)]/60"
              :style="{
                width: `${barPct(dish)}%`,
                transition: 'width var(--motion-slow) var(--ease-fluid)',
              }"
            />
          </div>
        </div>
      </li>
    </ol>

    <!-- Empty -->
    <div v-else-if="!loading" class="ui-empty-state p-5 text-center space-y-1">
      <p class="text-xs font-medium text-slate-300">{{ t('bestSellers.noData') }}</p>
      <p class="text-xs text-slate-400">{{ t('bestSellers.noDataHint') }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import { isFresh, readCache, writeCache } from '../lib/staleCache';

const { t, currentLocale } = useI18n();

const props = defineProps({
  period: { type: Number, default: 30 },
});

const mode = ref('count'); // 'count' | 'revenue'
const data = ref(null);
const loading = ref(false);
const updating = ref(false); // silently revalidating stale cache
const currency = ref('MAD');

const BEST_SELLERS_TTL_MS = 3 * 60 * 1000; // 3 minutes

const applyData = (d) => {
  data.value = d;
  currency.value = d?.currency || 'MAD';
};

const load = async () => {
  const cacheKey = `owner.best-sellers.${props.period}d`;
  const cached = readCache(cacheKey);

  if (cached) {
    applyData(cached);
    if (isFresh(cacheKey, BEST_SELLERS_TTL_MS)) return; // Still fresh — skip network
    updating.value = true; // Stale — revalidate silently
  } else {
    loading.value = true;
  }

  try {
    const { data: d } = await api.get('/owner/best-sellers/', { params: { period: props.period } });
    applyData(d);
    writeCache(cacheKey, d);
  } catch {
    // silent — stale data already showing if available
  } finally {
    loading.value = false;
    updating.value = false;
  }
};

const rows = computed(() => {
  if (!data.value) return [];
  return mode.value === 'count' ? (data.value.by_count || []) : (data.value.by_revenue || []);
});

const maxVal = computed(() => {
  if (!rows.value.length) return 1;
  return Math.max(...rows.value.map((r) => mode.value === 'count' ? r.total_qty : r.revenue), 1);
});

const barPct = (dish) => {
  const val = mode.value === 'count' ? dish.total_qty : dish.revenue;
  return Math.round((val / maxVal.value) * 100);
};

const fmtMoney = (amount) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency', currency: currency.value, maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${Number(amount).toFixed(0)}`;
  }
};

onMounted(load);
watch(() => props.period, load);
watch(currentLocale, load);
</script>
