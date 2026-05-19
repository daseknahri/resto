<template>
  <div>
    <!-- Header with toggle -->
    <div class="mb-3 flex items-center justify-between gap-2">
      <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">{{ t('bestSellers.title') }}</p>
      <div class="flex items-center gap-1">
        <button
          class="rounded-md px-2 py-0.5 text-[10px] font-semibold transition-colors"
          :class="mode === 'count' ? 'bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]' : 'text-slate-500 hover:text-slate-300'"
          @click="mode = 'count'"
        >{{ t('bestSellers.byOrders') }}</button>
        <button
          class="rounded-md px-2 py-0.5 text-[10px] font-semibold transition-colors"
          :class="mode === 'revenue' ? 'bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]' : 'text-slate-500 hover:text-slate-300'"
          @click="mode = 'revenue'"
        >{{ t('bestSellers.byRevenue') }}</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-1.5">
      <div v-for="i in 5" :key="i" class="h-7 animate-pulse rounded-lg bg-slate-800/60" />
    </div>

    <!-- Rows -->
    <ol v-else-if="rows.length" class="space-y-1.5">
      <li
        v-for="(dish, idx) in rows"
        :key="dish.dish_slug"
        class="flex items-center gap-2.5"
      >
        <!-- Rank -->
        <span class="w-4 shrink-0 text-center text-[10px] font-bold"
          :class="idx === 0 ? 'text-amber-400' : idx === 1 ? 'text-slate-300' : idx === 2 ? 'text-amber-700' : 'text-slate-600'"
        >{{ idx + 1 }}</span>

        <!-- Bar + label -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between gap-1 mb-0.5">
            <span class="truncate text-xs font-medium text-slate-200">{{ dish.dish_name }}</span>
            <span class="shrink-0 text-[10px] text-slate-400">
              {{ mode === 'count' ? t('bestSellers.qty', { n: dish.total_qty }) : fmtMoney(dish.revenue) }}
            </span>
          </div>
          <div class="h-1 rounded-full bg-slate-800/70 overflow-hidden">
            <div
              class="h-full rounded-full bg-[var(--color-secondary)]/60 transition-all duration-500"
              :style="{ width: `${barPct(dish)}%` }"
            />
          </div>
        </div>
      </li>
    </ol>

    <!-- Empty -->
    <p v-else-if="!loading" class="text-xs text-slate-500">{{ t('bestSellers.noData') }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const { t, currentLocale } = useI18n();

const props = defineProps({
  period: { type: Number, default: 30 },
});

const mode = ref('count'); // 'count' | 'revenue'
const data = ref(null);
const loading = ref(false);
const currency = ref('USD');

const load = async () => {
  loading.value = true;
  try {
    const { data: d } = await api.get('/owner/best-sellers/', { params: { period: props.period } });
    data.value = d;
    currency.value = d.currency || 'USD';
  } catch {
    // silent
  } finally {
    loading.value = false;
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
