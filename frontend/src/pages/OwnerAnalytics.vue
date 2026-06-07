<template>
  <section class="space-y-3 pb-24 sm:pb-6" aria-labelledby="analytics-heading">
    <article class="ui-workspace-stage ui-reveal space-y-3 p-3 sm:p-4">
      <!-- Header + period selector -->
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1.5">
          <p class="ui-kicker">{{ t("ownerAnalytics.kicker") }}</p>
          <h2 id="analytics-heading" class="ui-display text-xl font-semibold leading-tight tracking-tight text-white sm:text-2xl">{{ t("ownerAnalytics.title") }}</h2>
        </div>
        <div class="flex shrink-0 flex-wrap items-center gap-1" role="group" :aria-label="t('ownerHome.periodLabel')">
          <button
            v-for="d in PERIOD_OPTIONS"
            :key="d"
            class="ui-press ui-touch-target inline-flex items-center justify-center rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
            :class="insightsPeriod === d
              ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
              : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-200'"
            :aria-pressed="insightsPeriod === d"
            :aria-label="d + ' ' + t('ownerAnalytics.daysSuffix')"
            @click="insightsPeriod = d"
          >{{ d }}d</button>
        </div>
      </div>

      <!-- KPI cards: loading skeleton -->
      <div v-if="insightsLoading" class="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5" aria-hidden="true">
        <div v-for="i in 5" :key="i" class="ui-skeleton h-24" />
      </div>

      <!-- KPI cards: today stats + 7-day sparklines -->
      <div v-else class="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
        <div
          class="ui-admin-subcard ui-reveal space-y-1.5"
          :style="{ '--ui-delay': '0ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerHome.todayOrders") }}</p>
          <div class="flex items-end justify-between gap-1">
            <p class="ui-stat-value tabular-nums text-slate-100">{{ todayStats.count }}</p>
            <span
              v-if="yesterdayStats.count > 0"
              class="mb-0.5 text-[10px] tabular-nums"
              :class="todayStats.count >= yesterdayStats.count ? 'text-emerald-500' : 'text-slate-500'"
              :aria-label="t('ownerAnalytics.deltaLabel', { delta: todayStats.count - yesterdayStats.count })"
            >{{ todayStats.count >= yesterdayStats.count ? '+' : '' }}{{ todayStats.count - yesterdayStats.count }}</span>
          </div>
          <SparklineChart :values="sparklineOrders" :color="trend(sparklineOrders) === 'up' ? 'emerald' : 'slate'" :height="28" :label="t('ownerAnalytics.sparklineOrders')" />
        </div>

        <div
          class="ui-admin-subcard ui-reveal space-y-1.5"
          :style="{ '--ui-delay': '28ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerHome.todayRevenue") }}</p>
          <p class="ui-stat-value tabular-nums text-[var(--color-secondary)]">{{ todayStats.revenue }}</p>
          <SparklineChart :values="sparklineRevenue" color="secondary" :height="28" :label="t('ownerAnalytics.sparklineRevenue')" />
        </div>

        <div
          class="ui-admin-subcard ui-reveal space-y-1.5"
          :style="{ '--ui-delay': '56ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerHome.kpiAvgTicket") }}</p>
          <p class="ui-stat-value tabular-nums text-slate-100">{{ avgTicketLabel }}</p>
          <SparklineChart :values="sparklineAvgTicket" :color="trend(sparklineAvgTicket) === 'up' ? 'emerald' : 'slate'" :height="28" :label="t('ownerAnalytics.sparklineAvgTicket')" />
        </div>

        <div
          class="ui-admin-subcard ui-reveal space-y-1.5"
          :class="todayStats.pending > 0 ? 'border-amber-500/30' : ''"
          :style="{ '--ui-delay': '84ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerOrders.todayPending") }}</p>
          <div class="flex items-center gap-1.5">
            <p class="ui-stat-value tabular-nums" :class="todayStats.pending > 0 ? 'text-amber-400' : 'text-slate-100'">{{ todayStats.pending }}</p>
            <AppIcon v-if="todayStats.pending > 0" name="info" class="h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden="true" />
          </div>
          <div class="h-7" />
        </div>

        <RouterLink
          :to="{ name: 'owner-reservations' }"
          class="ui-admin-subcard ui-reveal ui-surface-lift space-y-1.5"
          :class="todayNewReservations > 0 ? 'border-sky-500/30' : 'hover:border-slate-600'"
          :style="{ '--ui-delay': '112ms' }"
        >
          <p class="ui-stat-label">{{ t("ownerHome.todayReservations") }}</p>
          <p class="ui-stat-value tabular-nums" :class="todayReservations === null ? 'text-slate-700' : todayNewReservations > 0 ? 'text-sky-400' : 'text-slate-100'">
            {{ todayReservations === null ? "—" : todayReservations }}
          </p>
          <p class="flex items-center gap-1 text-[10px] text-slate-500">
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
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";

import AppIcon from "../components/AppIcon.vue";
import BestSellersWidget from "../components/BestSellersWidget.vue";
import RevenueBarChart from "../components/RevenueBarChart.vue";
import OwnerDashboardInsights from "../components/OwnerDashboardInsights.vue";
import OwnerDashboardRevenue from "../components/OwnerDashboardRevenue.vue";
import SparklineChart from "../components/SparklineChart.vue";
import { useI18n } from "../composables/useI18n";
import { useOrderStore } from "../stores/order";
import { useSessionStore } from "../stores/session";

defineOptions({ name: "OwnerAnalytics" });

const session = useSessionStore();
const order = useOrderStore();
const { t, formatNumber } = useI18n();

const PERIOD_OPTIONS = [7, 14, 30, 90];
const insightsPeriod = ref(30);
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
const todayStats = computed(() => {
  const today = new Date().toDateString();
  const todayOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === today);
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
  const yStr = y.toDateString();
  const yOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === yStr);
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
</script>
