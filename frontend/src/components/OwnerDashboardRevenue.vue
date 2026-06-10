<template>
  <!-- Only rendered when the parent passes data or is loading -->
  <article
    v-if="loading || data"
    class="ui-command-deck space-y-3 p-3 sm:space-y-4 sm:p-4"
  >
    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <p class="ui-kicker">{{ t("ownerHome.analyticsKicker") }}</p>
        <h3 class="inline-flex items-center gap-2 text-lg font-semibold text-white">
          <AppIcon name="download" class="owner-revenue-icon" aria-hidden="true" />
          <span>{{ t("ownerHome.revenueTitle") }}</span>
          <svg
            v-if="updating"
            aria-hidden="true"
            class="h-3.5 w-3.5 animate-spin text-slate-500"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <path d="M13.5 8a5.5 5.5 0 1 1-1.1-3.3M13.5 2v3.5H10" />
          </svg>
        </h3>
        <span role="status" aria-live="polite" class="sr-only">{{ updating ? t('ownerHome.updating') : '' }}</span>
      </div>
      <p class="ui-chip shrink-0">
        {{ data ? t("ownerHome.revenuePeriod", { days: data.days }) : `${period}d` }}
      </p>
    </div>

    <!-- KPI row skeleton -->
    <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <template v-if="loading">
        <div v-for="i in 4" :key="i" class="ui-stat-tile animate-pulse">
          <div class="h-3 w-16 rounded bg-slate-700/60" />
          <div class="mt-2 h-7 w-14 rounded bg-slate-700/40" />
        </div>
      </template>
      <template v-else-if="data">
        <div class="ui-stat-tile ui-reveal" :style="{ '--ui-delay': '0ms' }">
          <p class="ui-stat-label">{{ t("ownerHome.revenueTotal") }}</p>
          <p class="ui-stat-value tabular-nums text-[var(--color-secondary)]">{{ fmt(data.total_revenue) }}</p>
          <PeriodBadge :pct="data.prev_period?.revenue_change_pct" />
        </div>
        <div class="ui-stat-tile ui-reveal" :style="{ '--ui-delay': '28ms' }">
          <p class="ui-stat-label">{{ t("ownerHome.revenueOrders") }}</p>
          <p class="ui-stat-value tabular-nums text-slate-100">{{ data.order_count }}</p>
          <PeriodBadge :pct="data.prev_period?.order_change_pct" />
        </div>
        <div class="ui-stat-tile ui-reveal" :style="{ '--ui-delay': '56ms' }">
          <p class="ui-stat-label">{{ t("ownerHome.revenueAvg") }}</p>
          <p class="ui-stat-value tabular-nums text-slate-100">{{ fmt(data.avg_order_value) }}</p>
          <PeriodBadge :pct="data.prev_period?.avg_change_pct" />
        </div>
        <div class="ui-stat-tile ui-reveal" :style="{ '--ui-delay': '84ms' }">
          <p class="ui-stat-label">{{ t("ownerHome.customerReturnRate") }}</p>
          <p class="ui-stat-value tabular-nums" :class="returnRate !== null ? 'text-slate-100' : 'text-slate-600'">
            {{ returnRateLabel }}
          </p>
          <p v-if="returnRate !== null" class="ui-stat-note">
            {{ t("ownerHome.customerReturnRateHint", { count: data.customer_return?.total_customers }) }}
          </p>
        </div>
      </template>
    </div>

    <!-- Daily revenue mini-chart -->
    <div v-if="data && chartDays.length > 1" class="max-w-full space-y-1">
      <p class="ui-kicker">{{ t("ownerHome.dailyRevenueKicker") }}</p>
      <h4 class="text-sm font-medium text-slate-100">{{ t("ownerHome.revenueDailyChart") }}</h4>
      <div
        class="ui-scroll-row h-20 items-end gap-0.5"
        role="img"
        :aria-label="t('ownerHome.revenueDailyChartAriaLabel')"
      >
        <div
          v-for="day in chartDays"
          :key="day.date"
          class="flex flex-1 shrink-0 min-w-[0.5rem] flex-col items-center gap-0.5"
          :title="`${day.date}: ${fmt(day.revenue)} (${day.orders})`"
        >
          <div
            class="w-full rounded-sm bg-[var(--color-secondary)]/70 transition-colors hover:bg-[var(--color-secondary)]"
            :style="{ height: `${day.heightPct}%`, minHeight: day.revenue > 0 ? '2px' : '0' }"
          />
        </div>
      </div>
      <div class="flex justify-between text-[10px] tabular-nums text-slate-500" aria-hidden="true">
        <span>{{ chartDays[0]?.shortDate }}</span>
        <span>{{ chartDays[chartDays.length - 1]?.shortDate }}</span>
      </div>
    </div>

    <!-- Peak hours -->
    <div
      v-if="data && data.order_count > 0 && peakHoursBars.length"
      class="space-y-3 border-t border-slate-800/60 pt-2"
    >
      <p class="ui-kicker">{{ t("ownerHome.peakHoursKicker") }}</p>
      <h4 class="text-sm font-medium text-slate-100">{{ t("ownerHome.peakHoursTitle") }}</h4>
      <div class="grid gap-4 sm:grid-cols-2">
        <!-- By hour of day -->
        <div class="space-y-1.5">
          <h4 class="ui-stat-label">{{ t("ownerHome.peakHoursByHour") }}</h4>
          <div
            class="flex h-16 items-end gap-px overflow-hidden"
            role="img"
            :aria-label="t('ownerHome.peakHoursByHourAriaLabel')"
          >
            <div
              v-for="bar in peakHoursBars"
              :key="bar.hour"
              class="flex-1 rounded-sm transition-colors"
              :class="hourBarColor(bar.hour)"
              :style="{ height: `${bar.heightPct}%`, minHeight: bar.count > 0 ? '2px' : '0' }"
              :title="`${bar.hour}:00 — ${bar.count}`"
            />
          </div>
          <div class="flex justify-between text-[9px] tabular-nums text-slate-500" aria-hidden="true">
            <span>{{ t("ownerHome.peakHoursAxisHour0") }}</span><span>{{ t("ownerHome.peakHoursAxisHour6") }}</span><span>{{ t("ownerHome.peakHoursAxisHour12") }}</span><span>{{ t("ownerHome.peakHoursAxisHour18") }}</span><span>{{ t("ownerHome.peakHoursAxisHour23") }}</span>
          </div>
        </div>
        <!-- By day of week -->
        <div class="space-y-1.5">
          <h4 class="ui-stat-label">{{ t("ownerHome.peakHoursByDay") }}</h4>
          <div
            class="flex h-16 items-end gap-1"
            role="img"
            :aria-label="t('ownerHome.peakHoursByDayAriaLabel')"
          >
            <div
              v-for="bar in peakWeekdayBars"
              :key="bar.label"
              class="flex flex-1 flex-col items-center gap-0.5"
              :title="`${bar.label} — ${bar.count}`"
            >
              <div
                class="w-full rounded-sm bg-[var(--color-secondary)]/70 transition-colors hover:bg-[var(--color-secondary)]"
                :style="{ height: `${bar.heightPct}%`, minHeight: bar.count > 0 ? '2px' : '0' }"
              />
            </div>
          </div>
          <div class="flex justify-between text-[9px] text-slate-500" aria-hidden="true">
            <span v-for="bar in peakWeekdayBars" :key="bar.label">{{ bar.label }}</span>
          </div>
        </div>
      </div>

      <!-- 2D heatmap: day-of-week × hour-of-day ─────────────────────────── -->
      <div v-if="heatmapData.length && heatmapMax > 0" class="space-y-1.5">
        <h4 class="ui-stat-label">{{ t("ownerHome.peakHoursHeatmapTitle") }}</h4>
        <!-- Hour axis labels -->
        <div class="ms-6 flex justify-between pe-0.5 text-[9px] tabular-nums text-slate-500" aria-hidden="true">
          <span>0h</span><span>6h</span><span>12h</span><span>18h</span><span>23h</span>
        </div>
        <!-- Grid rows: 7 days × 24 hours -->
        <div role="img" :aria-label="t('ownerHome.peakHoursHeatmapAriaLabel')">
          <div v-for="(row, d) in heatmapData" :key="d" class="mb-0.5 flex items-center gap-1.5">
            <span class="w-4 shrink-0 text-end text-[9px] leading-none text-slate-500" aria-hidden="true">{{ heatmapDayLabels[d] }}</span>
            <div class="flex flex-1 gap-px">
              <div
                v-for="(count, h) in row"
                :key="h"
                class="h-3 flex-1 rounded-[2px]"
                :style="{ backgroundColor: heatColor(count) }"
                :title="`${heatmapDayLabels[d]} ${h}:00–${h}:59 — ${count}`"
              />
            </div>
          </div>
        </div>
        <!-- Legend -->
        <div class="ms-6 flex items-center gap-2 pe-0.5 text-[9px] text-slate-500" aria-hidden="true">
          <span>{{ t("ownerHome.peakHoursHeatmapLow") }}</span>
          <div class="flex gap-px">
            <div
              v-for="i in 5"
              :key="i"
              class="h-2 w-5 rounded-[2px]"
              :style="{ backgroundColor: `rgba(99,102,241,${(0.1 + (i - 1) * 0.2).toFixed(2)})` }"
            />
          </div>
          <span>{{ t("ownerHome.peakHoursHeatmapHigh") }}</span>
        </div>
      </div>
    </div>

    <!-- Popular dishes -->
    <div v-if="data && popularDishes.length" class="space-y-2 border-t border-slate-800/60 pt-2">
      <p class="ui-kicker">{{ t("ownerHome.popularDishesTitle") }}</p>
      <ol class="space-y-1.5">
        <li v-for="(dish, idx) in popularDishes" :key="dish.dish_slug" class="flex items-center gap-2 text-sm">
          <span class="w-4 shrink-0 text-end text-xs font-bold tabular-nums text-slate-600">{{ idx + 1 }}</span>
          <div class="relative h-6 flex-1 overflow-hidden rounded-sm bg-slate-800/50">
            <div
              class="absolute inset-y-0 start-0 rounded-sm bg-[var(--color-secondary)]/20 transition-all"
              :style="{ width: dish.barPct + '%' }"
            />
            <span class="relative truncate px-2 leading-6 text-slate-200">{{ dish.dish_name }}</span>
          </div>
          <span class="shrink-0 tabular-nums text-xs text-slate-400">×{{ dish.order_count }}</span>
          <span v-if="dish.total_revenue > 0" class="shrink-0 tabular-nums text-[10px] text-[var(--color-secondary)]/55">{{ fmt(dish.total_revenue) }}</span>
        </li>
      </ol>
    </div>

    <!-- Marketplace commission summary — only when restaurant has marketplace orders -->
    <div
      v-if="data && marketplaceStats.order_count > 0"
      class="space-y-2 border-t border-slate-800/60 pt-2"
    >
      <p class="ui-kicker">{{ t("ownerHome.marketplaceTitle") }}</p>
      <div class="grid grid-cols-3 gap-2">
        <div class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("ownerHome.marketplaceOrders") }}</p>
          <p class="ui-stat-value tabular-nums text-slate-100">{{ marketplaceStats.order_count }}</p>
        </div>
        <div class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("ownerHome.marketplaceRevenue") }}</p>
          <p class="ui-stat-value tabular-nums text-[var(--color-secondary)]">{{ fmt(marketplaceStats.revenue) }}</p>
        </div>
        <div class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("ownerHome.marketplaceCommission") }}</p>
          <p class="ui-stat-value tabular-nums text-rose-400">{{ fmt(marketplaceStats.commission_total) }}</p>
          <p class="ui-stat-note">{{ t("ownerHome.platformFeeNote") }}</p>
        </div>
      </div>
    </div>

    <!-- Fulfillment breakdown — pickup / delivery / table split -->
    <div
      v-if="loading || (data && data.order_count > 0)"
      class="pt-2 border-t border-slate-800/60"
    >
      <FulfillmentBreakdown
        :breakdown="data?.fulfillment_breakdown ?? {}"
        :loading="loading"
        :currency="data?.currency"
      />
    </div>
  </article>
</template>

<script setup>
import { computed } from "vue";
import AppIcon from "./AppIcon.vue";
import FulfillmentBreakdown from "./FulfillmentBreakdown.vue";
import PeriodBadge from "./PeriodBadge.vue";
import { useI18n } from "../composables/useI18n";
import { useTenantStore } from "../stores/tenant";

const { t, formatNumber, currentLocale } = useI18n();
const tenant = useTenantStore();

const props = defineProps({
  /** Revenue summary object from /owner/dashboard/ */
  data: { type: Object, default: null },
  /** true while insights are being fetched for the first time */
  loading: { type: Boolean, default: false },
  /** true while stale data is being silently revalidated */
  updating: { type: Boolean, default: false },
  /** Current analytics period in days */
  period: { type: Number, default: 30 },
});

// ── Formatters ────────────────────────────────────────────────────────────────
const fmt = (amount) => {
  const n = Number(amount) || 0;
  if (n === 0) return "—";
  const currency = props.data?.currency || tenant.meta?.profile?.currency || null;
  try {
    if (currency) return formatNumber(n, { style: "currency", currency });
  } catch { /* unsupported */ }
  return n.toFixed(2);
};

// ── Charts ────────────────────────────────────────────────────────────────────
const chartDays = computed(() => {
  const days = props.data?.daily || [];
  if (!days.length) return [];
  const maxRev = Math.max(...days.map((d) => d.revenue), 1);
  return days.map((d) => ({
    date: d.date,
    revenue: d.revenue,
    orders: d.orders,
    heightPct: Math.round((d.revenue / maxRev) * 100),
    shortDate: d.date.slice(5),
  }));
});

const hourBarColor = (hour) => {
  if (hour >= 6 && hour <= 11) return "bg-amber-400/70 hover:bg-amber-400";
  if (hour >= 12 && hour <= 14) return "bg-emerald-400/70 hover:bg-emerald-400";
  if (hour >= 18 && hour <= 22) return "bg-violet-400/70 hover:bg-violet-400";
  return "bg-slate-500/50 hover:bg-slate-400/60";
};

const peakHoursBars = computed(() => {
  const hours = props.data?.peak_hours?.by_hour || [];
  const max = Math.max(...hours, 1);
  return hours.map((count, hour) => ({ hour, count, heightPct: Math.round((count / max) * 100) }));
});

const peakWeekdayBars = computed(() => {
  const days = props.data?.peak_hours?.by_weekday || [];
  const max = Math.max(...days, 1);
  const labels = Array.from({ length: 7 }, (_, i) => {
    try { return new Intl.DateTimeFormat("en", { weekday: "short" }).format(new Date(2023, 0, 1 + i)); }
    catch { return ["Su","Mo","Tu","We","Th","Fr","Sa"][i]; }
  });
  return days.map((count, idx) => ({ label: labels[idx] || String(idx), count, heightPct: Math.round((count / max) * 100) }));
});

// ── Day×Hour heatmap ──────────────────────────────────────────────────────────
const heatmapData = computed(() => props.data?.peak_hours?.by_day_hour || []);

const heatmapMax = computed(() => {
  if (!heatmapData.value.length) return 0;
  return Math.max(...heatmapData.value.flat(), 1);
});

const heatmapDayLabels = computed(() => {
  // Jan 1 2023 was a Sunday → index 0-6 maps to Sun-Sat
  return Array.from({ length: 7 }, (_, i) => {
    try {
      return new Intl.DateTimeFormat(currentLocale.value, { weekday: "short" }).format(new Date(2023, 0, 1 + i));
    } catch {
      return ["Su","Mo","Tu","We","Th","Fr","Sa"][i];
    }
  });
});

const heatColor = (count) => {
  if (!heatmapMax.value || count === 0) return "rgba(30,41,59,0.6)";
  const alpha = 0.1 + (count / heatmapMax.value) * 0.82;
  return `rgba(99,102,241,${alpha.toFixed(3)})`;
};

const popularDishes = computed(() => {
  const dishes = props.data?.popular_dishes || [];
  const maxCount = Math.max(...dishes.map((d) => d.order_count), 1);
  return dishes.map((d) => ({ ...d, barPct: Math.round((d.order_count / maxCount) * 100) }));
});

// ── Marketplace stats ─────────────────────────────────────────────────────────
const marketplaceStats = computed(() => ({
  order_count: props.data?.marketplace?.order_count || 0,
  revenue: props.data?.marketplace?.revenue || 0,
  commission_total: props.data?.marketplace?.commission_total || 0,
}));

// ── Return rate ───────────────────────────────────────────────────────────────
const returnRate = computed(() => {
  const d = props.data?.customer_return;
  if (!d || d.return_rate_pct === null || d.return_rate_pct === undefined) return null;
  return d.return_rate_pct;
});
const returnRateLabel = computed(() =>
  returnRate.value !== null ? `${returnRate.value.toFixed(1)}%` : t("ownerHome.customerReturnRateNA")
);
</script>

<style scoped>
.owner-revenue-icon { width: 1rem; height: 1rem; color: var(--color-secondary); }
</style>
