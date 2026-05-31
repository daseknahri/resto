<template>
  <div class="revenue-chart-wrap">
    <!-- Period selector — hidden when parent supplies data -->
    <div class="mb-3 flex items-center justify-between gap-2">
      <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">{{ t('revenueChart.title') }}</p>
      <div v-if="!externalDays" class="flex items-center gap-1">
        <button
          v-for="p in periods"
          :key="p"
          class="rounded-md px-2 py-0.5 text-[10px] font-semibold transition-colors"
          :class="period === p
            ? 'bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]'
            : 'text-slate-500 hover:text-slate-300'"
          :aria-pressed="period === p"
          @click="setPeriod(p)"
        >{{ p }}d</button>
        <button
          class="ml-1 text-slate-500 hover:text-slate-300 transition-colors"
          :aria-label="t('common.refresh')"
          :disabled="loading"
          @click="load"
        >
          <svg aria-hidden="true" class="h-3 w-3" :class="loading ? 'animate-spin' : ''" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Summary row -->
    <div class="mb-3 grid grid-cols-3 gap-2 text-center">
      <div>
        <p class="text-base font-bold tabular-nums text-[var(--color-secondary)]">{{ fmtMoney(totalRevenue) }}</p>
        <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t('revenueChart.totalRevenue') }}</p>
      </div>
      <div>
        <p class="text-base font-bold tabular-nums text-white">{{ totalOrders }}</p>
        <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t('revenueChart.totalOrders') }}</p>
      </div>
      <div>
        <p class="text-base font-bold tabular-nums text-slate-200">{{ totalOrders ? fmtMoney(totalRevenue / totalOrders) : '—' }}</p>
        <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t('revenueChart.avgOrder') }}</p>
      </div>
    </div>

    <!-- SVG bar chart -->
    <div v-if="!loading && !parentLoading && days.length" class="relative">
      <svg
        :viewBox="`0 0 ${SVG_W} ${SVG_H}`"
        class="w-full overflow-visible"
        role="img"
        :aria-label="t('revenueChart.title')"
        @mouseleave="tooltip = null"
      >
        <!-- Y-axis guide lines -->
        <line
          v-for="(line, i) in yLines"
          :key="i"
          :x1="CHART_L"
          :y1="line.y"
          :x2="CHART_L + CHART_W"
          :y2="line.y"
          stroke="rgba(51,65,85,0.45)"
          stroke-width="0.5"
        />

        <!-- Bars -->
        <g v-for="(day, i) in days" :key="day.date">
          <!-- Hover hit area -->
          <rect
            :x="barX(i) - barGap / 2"
            :y="CHART_T"
            :width="barWidth + barGap"
            :height="CHART_H"
            fill="transparent"
            class="cursor-pointer"
            @mouseenter="onBarHover(day, barX(i), barY(day.revenue))"
          />
          <!-- Bar fill -->
          <rect
            :x="barX(i)"
            :y="barY(day.revenue)"
            :width="barWidth"
            :height="CHART_T + CHART_H - barY(day.revenue)"
            :rx="barWidth < 8 ? 1 : 2"
            :fill="tooltip?.date === day.date ? 'var(--color-secondary)' : 'rgba(20,184,166,0.35)'"
            class="transition-colors"
          />
          <!-- X-axis date label — show every Nth label to avoid crowding -->
          <text
            v-if="i % xLabelStep === 0"
            :x="barX(i) + barWidth / 2"
            :y="SVG_H - 1"
            text-anchor="middle"
            font-size="5.5"
            fill="rgba(148,163,184,0.7)"
          >{{ fmtDateShort(day.date) }}</text>
        </g>

        <!-- Tooltip -->
        <g v-if="tooltip">
          <!-- Pin line -->
          <line
            :x1="tooltip.cx"
            :y1="CHART_T"
            :x2="tooltip.cx"
            :y2="CHART_T + CHART_H"
            stroke="rgba(245,158,11,0.5)"
            stroke-width="0.7"
            stroke-dasharray="2,2"
          />
          <!-- Bubble -->
          <rect
            :x="tooltipBubble.x"
            :y="tooltipBubble.y"
            :width="tooltipBubble.w"
            :height="tooltipBubble.h"
            rx="4"
            fill="rgba(2,6,23,0.92)"
            stroke="rgba(51,65,85,0.9)"
            stroke-width="0.7"
          />
          <text
            :x="tooltipBubble.x + tooltipBubble.w / 2"
            :y="tooltipBubble.y + 6.5"
            text-anchor="middle"
            font-size="5"
            font-weight="600"
            fill="rgba(245,158,11,0.95)"
          >{{ fmtDateLong(tooltip.date) }}</text>
          <text
            :x="tooltipBubble.x + tooltipBubble.w / 2"
            :y="tooltipBubble.y + 13"
            text-anchor="middle"
            font-size="5.5"
            font-weight="700"
            fill="white"
          >{{ fmtMoney(tooltip.revenue) }}</text>
          <text
            :x="tooltipBubble.x + tooltipBubble.w / 2"
            :y="tooltipBubble.y + 19.5"
            text-anchor="middle"
            font-size="5"
            fill="rgba(148,163,184,0.8)"
          >{{ t('revenueChart.orders', { count: tooltip.order_count }) }}</text>
        </g>
      </svg>
    </div>

    <!-- Loading skeleton (own fetch or parent still fetching) -->
    <div v-else-if="loading || parentLoading" class="h-28 animate-pulse rounded-xl bg-slate-800/50" />

    <!-- Error / empty -->
    <div v-else class="py-8 text-center text-xs text-slate-500">
      {{ error ? t('revenueChart.loadError') : t('revenueChart.noData') }}
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const { t, currentLocale } = useI18n();

// ── Props ─────────────────────────────────────────────────────────────────────
const props = defineProps({
  initialPeriod: { type: Number, default: 14 },
  /** When set by a parent (e.g. OwnerHome), skip the API call and use this data directly. */
  externalDays: { type: Array, default: null },
  externalCurrency: { type: String, default: null },
  /**
   * When true the parent is still fetching — show skeleton without making our own
   * API call.  When it turns false without externalDays arriving, fall back to own fetch.
   */
  parentLoading: { type: Boolean, default: false },
});

// ── State ─────────────────────────────────────────────────────────────────────
const periods = [7, 14, 30];
const period = ref(props.initialPeriod);
const days = ref([]);
const currency = ref('MAD');
const loading = ref(false);
const error = ref(false);
const tooltip = ref(null);

// ── SVG layout constants ──────────────────────────────────────────────────────
const SVG_W = 360;
const SVG_H = 80;
const CHART_L = 0;
const CHART_T = 4;
const CHART_W = SVG_W;
const CHART_H = SVG_H - CHART_T - 10; // bottom 10 px for x labels

// ── Computed layout ───────────────────────────────────────────────────────────
const maxRevenue = computed(() => Math.max(...days.value.map((d) => d.revenue), 1));
const totalRevenue = computed(() => days.value.reduce((s, d) => s + d.revenue, 0));
const totalOrders = computed(() => days.value.reduce((s, d) => s + d.order_count, 0));

const barGap = computed(() => Math.max(1, Math.floor((CHART_W / days.value.length) * 0.18)));
const barWidth = computed(() =>
  days.value.length ? Math.max(2, (CHART_W / days.value.length) - barGap.value) : 10
);

const barX = (i) => CHART_L + i * (barWidth.value + barGap.value);
const barY = (revenue) => {
  const pct = revenue / maxRevenue.value;
  return CHART_T + CHART_H * (1 - pct);
};

const xLabelStep = computed(() => {
  if (days.value.length <= 7) return 1;
  if (days.value.length <= 14) return 2;
  return 5;
});

// Y guide lines at 25%, 50%, 75%, 100%
const yLines = computed(() =>
  [0.25, 0.5, 0.75, 1].map((pct) => ({
    y: CHART_T + CHART_H * (1 - pct),
    value: maxRevenue.value * pct,
  }))
);

// Tooltip bubble positioning
const tooltipBubble = computed(() => {
  if (!tooltip.value) return { x: 0, y: 0, w: 56, h: 24 };
  const w = 56;
  const h = 24;
  let x = tooltip.value.cx - w / 2;
  if (x < 0) x = 0;
  if (x + w > SVG_W) x = SVG_W - w;
  const y = Math.max(CHART_T + 2, tooltip.value.barY - h - 4);
  return { x, y, w, h };
});

// ── External data (parent-supplied, no API call needed) ───────────────────────
watch(
  () => props.externalDays,
  (incoming) => {
    if (!incoming) return;
    // Normalize field name: parent uses 'orders', chart expects 'order_count'
    days.value = incoming.map((d) => ({
      ...d,
      order_count: d.order_count ?? d.orders ?? 0,
    }));
    if (props.externalCurrency) currency.value = props.externalCurrency;
  },
  { immediate: true }
);

// ── API ───────────────────────────────────────────────────────────────────────
const load = async () => {
  if (props.externalDays) return;    // parent supplies data — skip network
  if (props.parentLoading) return;   // parent is still fetching — wait for watcher
  loading.value = true;
  error.value = false;
  try {
    const { data } = await api.get('/owner/revenue-chart/', {
      params: { period: period.value },
    });
    days.value = data.days || [];
    currency.value = data.currency || 'MAD';
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const setPeriod = (p) => {
  if (period.value === p) return;
  period.value = p;
  load();
};

// ── Formatters ────────────────────────────────────────────────────────────────
const fmtMoney = (amount) => {
  if (!amount && amount !== 0) return '—';
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency: currency.value,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${Number(amount).toFixed(0)}`;
  }
};

const fmtDateShort = (iso) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      month: 'numeric', day: 'numeric',
    }).format(new Date(iso));
  } catch {
    return iso?.slice(5) ?? '';
  }
};

const fmtDateLong = (iso) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      month: 'short', day: 'numeric',
    }).format(new Date(iso));
  } catch {
    return iso?.slice(5) ?? '';
  }
};

// ── Interactions ──────────────────────────────────────────────────────────────
const onBarHover = (day, cx, by) => {
  tooltip.value = {
    date: day.date,
    revenue: day.revenue,
    order_count: day.order_count,
    cx: cx + barWidth.value / 2,
    barY: by,
  };
};

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => { if (!props.externalDays) load(); });
watch(currentLocale, () => { if (!props.externalDays) load(); });

// When parent finishes loading without supplying external data (e.g. API error on
// the dashboard endpoint), fall back to our own fetch so the chart isn't blank.
watch(
  () => props.parentLoading,
  (nowLoading) => {
    if (!nowLoading && !props.externalDays && !days.value.length) load();
  },
);
</script>
