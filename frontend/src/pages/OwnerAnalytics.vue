<template>
  <section class="space-y-4 pb-24 sm:pb-6" aria-labelledby="analytics-heading" :aria-busy="insightsLoading">
    <article class="ui-workspace-stage ui-reveal space-y-4 p-4 sm:p-5">
      <!-- Header + period selector -->
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t("ownerAnalytics.kicker") }}</p>
          <h2 id="analytics-heading" class="ui-display text-2xl font-semibold leading-tight tracking-tight text-white sm:text-3xl">{{ t("ownerAnalytics.title") }}</h2>
        </div>
        <div class="flex shrink-0 flex-wrap items-center gap-1.5">
          <!-- Period buttons -->
          <div role="group" :aria-label="t('ownerHome.periodLabel')" class="flex flex-wrap items-center gap-1.5">
            <button
              v-for="d in PERIOD_OPTIONS"
              :key="d"
              class="ui-press inline-flex items-center justify-center rounded-full border px-3.5 py-1.5 text-[11px] font-semibold tracking-wide transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
              :class="insightsPeriod === d
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)] shadow-sm shadow-[var(--color-secondary)]/10'
                : 'border-slate-700/80 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
              :aria-pressed="insightsPeriod === d"
              :aria-label="d === 1 ? t('ownerAnalytics.periodToday') : d + ' ' + t('ownerAnalytics.daysSuffix')"
              @click="insightsPeriod = d"
            >{{ d === 1 ? t('ownerAnalytics.periodToday') : d + 'd' }}</button>
          </div>
          <!-- Export CSV -->
          <button
            type="button"
            class="ui-press inline-flex items-center gap-1.5 rounded-full border border-slate-700/80 px-3 py-1.5 text-[11px] font-semibold text-slate-400 transition-colors hover:border-slate-500 hover:text-slate-200 disabled:opacity-50"
            :disabled="analyticsExporting"
            :aria-label="t('ownerAnalytics.exportCsv')"
            @click="exportAnalyticsCsv"
          >
            <AppIcon name="download" class="h-3 w-3 shrink-0" aria-hidden="true" />
            {{ analyticsExporting ? t("common.loading") : t("ownerAnalytics.exportCsv") }}
          </button>
        </div>
      </div>

      <!-- KPI cards: loading skeleton -->
      <div v-if="insightsLoading" class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-5" aria-hidden="true">
        <div v-for="i in 5" :key="i" class="ui-skeleton h-28" />
      </div>

      <!-- KPI cards: today stats + 7-day sparklines -->
      <div v-else class="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-5">
        <div
          class="ui-admin-subcard ui-reveal space-y-2 p-3"
          :style="{ '--ui-delay': '0ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerHome.todayOrders") }}</p>
          <div class="flex items-end justify-between gap-1">
            <p class="ui-stat-value tabular-nums text-slate-100 !mt-0 text-[1.6rem]">{{ todayStats.count }}</p>
            <span
              v-if="yesterdayStats.count > 0"
              class="mb-0.5 inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold tabular-nums"
              :class="todayStats.count >= yesterdayStats.count ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-800/60 text-slate-500'"
              :aria-label="t('ownerAnalytics.deltaLabel', { delta: todayStats.count - yesterdayStats.count })"
            >{{ todayStats.count >= yesterdayStats.count ? '+' : '' }}{{ todayStats.count - yesterdayStats.count }}</span>
          </div>
          <SparklineChart :values="sparklineOrders" :color="trend(sparklineOrders) === 'up' ? 'emerald' : 'slate'" :height="28" :label="t('ownerAnalytics.sparklineOrders')" />
        </div>

        <div
          class="ui-admin-subcard ui-reveal space-y-2 p-3"
          :style="{ '--ui-delay': '28ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerHome.todayRevenue") }}</p>
          <div class="flex items-end gap-1.5">
            <p class="ui-stat-value tabular-nums !mt-0 text-[1.6rem] text-[var(--color-secondary)]">{{ todayStats.revenue }}</p>
            <span
              v-if="yesterdayStats.revenue > 0"
              class="mb-1 text-[10px] tabular-nums"
              :class="todayStats.revenueRaw >= yesterdayStats.revenue ? 'text-emerald-400' : 'text-slate-500'"
            >{{ todayStats.revenueRaw >= yesterdayStats.revenue ? '+' : '' }}{{ Math.round((todayStats.revenueRaw - yesterdayStats.revenue) / yesterdayStats.revenue * 100) }}%</span>
          </div>
          <SparklineChart :values="sparklineRevenue" color="secondary" :height="28" :label="t('ownerAnalytics.sparklineRevenue')" />
        </div>

        <div
          class="ui-admin-subcard ui-reveal space-y-2 p-3"
          :style="{ '--ui-delay': '56ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerHome.kpiAvgTicket") }}</p>
          <p class="ui-stat-value tabular-nums !mt-0 text-[1.6rem] text-slate-100">{{ avgTicketLabel }}</p>
          <SparklineChart :values="sparklineAvgTicket" :color="trend(sparklineAvgTicket) === 'up' ? 'emerald' : 'slate'" :height="28" :label="t('ownerAnalytics.sparklineAvgTicket')" />
        </div>

        <div
          class="ui-admin-subcard ui-reveal space-y-2 p-3"
          :class="todayStats.pending > 0 ? 'border-amber-500/30' : ''"
          :style="{ '--ui-delay': '84ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerOrders.todayPending") }}</p>
          <div class="flex items-center gap-1.5">
            <p class="ui-stat-value tabular-nums !mt-0 text-[1.6rem]" :class="todayStats.pending > 0 ? 'text-amber-400' : 'text-slate-100'">{{ todayStats.pending }}</p>
            <AppIcon v-if="todayStats.pending > 0" name="info" class="h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden="true" />
          </div>
          <div class="h-7" />
        </div>

        <RouterLink
          v-if="tenant.capabilities.reservations !== false"
          :to="{ name: 'owner-reservations' }"
          class="ui-admin-subcard ui-reveal ui-surface-lift space-y-2 p-3"
          :class="todayNewReservations > 0 ? 'border-sky-500/30' : 'hover:border-slate-600'"
          :style="{ '--ui-delay': '112ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerHome.todayReservations") }}</p>
          <p class="ui-stat-value tabular-nums !mt-0 text-[1.6rem]" :class="todayReservations === null ? 'text-slate-700' : todayNewReservations > 0 ? 'text-sky-400' : 'text-slate-100'">
            {{ todayReservations === null ? "—" : todayReservations }}
          </p>
          <p class="flex items-center gap-1 text-[10px] font-medium tracking-wide text-slate-500">
            <span>{{ t("ownerHome.viewReservations") }}</span>
            <span class="ltr:inline rtl:hidden" aria-hidden="true">→</span>
            <span class="ltr:hidden rtl:inline" aria-hidden="true">←</span>
          </p>
        </RouterLink>
      </div>

      <!-- Revenue chart + best sellers -->
      <div class="grid gap-3 xl:grid-cols-2">
        <div class="ui-panel p-3 sm:p-4">
          <RevenueBarChart :external-days="chartDays" :external-currency="chartCurrency" :parent-loading="insightsLoading" />
        </div>
        <div class="ui-panel p-3 sm:p-4">
          <BestSellersWidget :period="insightsPeriod" />
        </div>
      </div>
    </article>

    <!-- Repeat-business panel (B2) -->
    <RepeatAnalyticsWidget :period="insightsPeriod" />

    <!-- Insights (owns the /owner/dashboard/ fetch) -->
    <OwnerDashboardInsights
      :period="insightsPeriod"
      :category-name-by-slug="categoryNameBySlug"
      :dish-name-by-slug="dishNameBySlug"
      @data="onInsightsData"
      @period-change="insightsPeriod = $event"
      @loading-change="insightsLoading = $event"
      @updating-change="insightsUpdating = $event"
    />

    <!-- Revenue (permission-gated) -->
    <OwnerDashboardRevenue
      v-if="session.canViewRevenue"
      :data="revenueSummary"
      :loading="insightsLoading"
      :updating="insightsUpdating"
      :period="insightsPeriod"
    />
  </section>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import AppIcon from "../components/AppIcon.vue";
import BestSellersWidget from "../components/BestSellersWidget.vue";
import RevenueBarChart from "../components/RevenueBarChart.vue";
import OwnerDashboardInsights from "../components/OwnerDashboardInsights.vue";
import RepeatAnalyticsWidget from "../components/RepeatAnalyticsWidget.vue";
import OwnerDashboardRevenue from "../components/OwnerDashboardRevenue.vue";
import SparklineChart from "../components/SparklineChart.vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import { useOrderStore } from "../stores/order";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";
import api from "../lib/api";

defineOptions({ name: "OwnerAnalytics" });

const session = useSessionStore();
const order = useOrderStore();
const tenant = useTenantStore();
const toast = useToastStore();
const { t, formatNumber } = useI18n();

const PERIOD_OPTIONS = [1, 7, 14, 30, 90];
const LS_PERIOD_KEY = "owner.analytics.period";
const _storedPeriod = Number(localStorage.getItem(LS_PERIOD_KEY));
const insightsPeriod = ref(PERIOD_OPTIONS.includes(_storedPeriod) ? _storedPeriod : 7);
watch(insightsPeriod, (val) => { localStorage.setItem(LS_PERIOD_KEY, String(val)); });
const insightsLoading = ref(true);
const insightsUpdating = ref(false);
const revenueSummary = ref(null);
const todayReservations = ref(null);
const todayNewReservations = ref(0);
// Category/dish label maps for the insights breakdowns are populated lazily by
// the insights component itself (it falls back to slugs if absent).
const categoryNameBySlug = ref({});
const dishNameBySlug = ref({});

const onInsightsData = (data) => {
  insightsLoading.value = false;
  if (data?.today_reservations !== undefined) {
    todayReservations.value = data.today_reservations;
    todayNewReservations.value = data.today_new_reservations ?? 0;
  }
  if (data?.revenue_summary) {
    revenueSummary.value = {
      ...data.revenue_summary,
      fulfillment_breakdown: data.revenue_summary.fulfillment_breakdown ?? {},
    };
  }
};

// ── Today's order stats — from the order store (no extra fetch) ──
// Uses tenant timezone (Contract E) so "today" aligns with the restaurant's local day.
const _fmtDate = (d) => {
  const tz = tenant.resolvedMeta?.profile?.timezone;
  if (!tz) return d.toDateString();
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  } catch { return d.toDateString(); }
};

const todayStats = computed(() => {
  const today = _fmtDate(new Date());
  const todayOrders = order.orders.filter((o) => _fmtDate(new Date(o.created_at)) === today);
  const revenue = todayOrders.reduce((s, o) => s + (Number(o.total) || 0), 0);
  const currency = todayOrders.find((o) => o.currency)?.currency || "MAD";
  let revenueLabel = "";
  try {
    revenueLabel = formatNumber(revenue, { style: "currency", currency, notation: "compact", maximumFractionDigits: 0 });
  } catch {
    revenueLabel = `${currency} ${Math.floor(revenue)}`;
  }
  return { count: todayOrders.length, revenue: revenueLabel, revenueRaw: revenue, pending: todayOrders.filter((o) => o.status === "pending").length };
});

const avgTicketLabel = computed(() => {
  const { count, revenueRaw } = todayStats.value;
  if (!count) return "—";
  const currency = order.orders.find((o) => o.currency)?.currency || "MAD";
  try { return formatNumber(revenueRaw / count, { style: "currency", currency, maximumFractionDigits: 0 }); }
  catch { return `${currency} ${Math.round(revenueRaw / count)}`; }
});

const yesterdayStats = computed(() => {
  const y = new Date();
  y.setDate(y.getDate() - 1);
  const yStr = _fmtDate(y);
  const yOrders = order.orders.filter((o) => _fmtDate(new Date(o.created_at)) === yStr);
  return { count: yOrders.length, revenue: yOrders.reduce((s, o) => s + (Number(o.total) || 0), 0) };
});

// ── Sparklines from the revenue summary daily breakdown ──
const sparklineRevenue = computed(() => (revenueSummary.value?.daily || []).slice(-7).map((d) => Number(d.revenue) || 0));
const sparklineOrders = computed(() => (revenueSummary.value?.daily || []).slice(-7).map((d) => Number(d.orders) || 0));
const sparklineAvgTicket = computed(() => (revenueSummary.value?.daily || []).slice(-7).map((d) => {
  const rev = Number(d.revenue) || 0;
  const orders = Number(d.orders) || 0;
  return orders > 0 ? rev / orders : 0;
}));

const trend = (values) => {
  if (values.length < 2) return "neutral";
  const first = values[0];
  const last = values[values.length - 1];
  if (last > first * 1.02) return "up";
  if (last < first * 0.98) return "down";
  return "neutral";
};

const chartDays = computed(() => {
  const days = revenueSummary.value?.daily;
  if (!days?.length) return null;
  return days.map((d) => ({ date: d.date, revenue: d.revenue, order_count: d.orders ?? 0 }));
});
const chartCurrency = computed(() => revenueSummary.value?.currency ?? null);

// ── Analytics CSV export ─────────────────────────────────────────────────────
const analyticsExporting = ref(false);
const exportAnalyticsCsv = async () => {
  if (analyticsExporting.value) return;
  analyticsExporting.value = true;
  try {
    const resp = await api.get("/owner/analytics/export/", {
      params: { days: insightsPeriod.value },
      responseType: "blob",
    });
    const url = URL.createObjectURL(new Blob([resp.data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = `analytics-${insightsPeriod.value}d.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.show(t('ownerAnalytics.exportDone'), 'success', 3000);
  } catch {
    toast.show(t('ownerAnalytics.exportFailed'), 'error');
  } finally {
    analyticsExporting.value = false;
  }
};
</script>
