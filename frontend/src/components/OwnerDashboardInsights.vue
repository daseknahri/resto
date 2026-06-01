<template>
  <article class="ui-command-deck space-y-3 p-3 sm:space-y-4 sm:p-4">
    <!-- Section header -->
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 class="inline-flex items-center gap-2 text-lg font-semibold">
        <AppIcon name="chart" class="owner-insights-icon" />
        <span>{{ t("ownerHome.analyticsTitle", { days: internalPeriod }) }}</span>
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
      <div class="flex flex-wrap items-center gap-2">
        <!-- Period selector -->
        <div class="flex items-center gap-1">
          <button
            v-for="d in PERIOD_OPTIONS"
            :key="d"
            class="rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition-colors"
            :class="
              internalPeriod === d
                ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
                : 'border-slate-700 text-slate-400 hover:border-slate-600 hover:text-slate-200'
            "
            :aria-pressed="internalPeriod === d"
            :disabled="loading"
            @click="setPeriod(d)"
          >
            {{ d }}d
          </button>
        </div>
        <button
          class="inline-flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-800/60 px-2.5 py-1 text-xs text-slate-300 transition hover:border-slate-600 hover:text-white"
          :disabled="exporting"
          @click="exportCsv"
        >
          <svg v-if="!exporting" aria-hidden="true" class="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 11v2a1 1 0 001 1h10a1 1 0 001-1v-2M8 2v8M5 7l3 3 3-3" />
          </svg>
          <svg v-else aria-hidden="true" class="h-3.5 w-3.5 animate-spin" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="8" cy="8" r="6" stroke-dasharray="28" stroke-dashoffset="10" />
          </svg>
          {{ t("ownerHome.exportCsv") }}
        </button>
      </div>
    </div>

    <!-- KPI tiles skeleton -->
    <div class="grid grid-cols-2 gap-2 sm:gap-3 xl:grid-cols-4">
      <template v-if="loading">
        <div v-for="i in 4" :key="i" class="ui-stat-tile animate-pulse">
          <div class="h-3 w-16 rounded bg-slate-700/60" />
          <div class="mt-2 h-7 w-12 rounded bg-slate-700/40" />
        </div>
      </template>
      <template v-else>
        <div class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("ownerHome.menuViews") }}</p>
          <p class="ui-stat-value text-slate-100">{{ counts.menu_view || 0 }}</p>
        </div>
        <div class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("ownerHome.dishViews") }}</p>
          <p class="ui-stat-value text-slate-100">{{ counts.dish_view || 0 }}</p>
        </div>
        <div class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("ownerHome.orderActions") }}</p>
          <p class="ui-stat-value text-slate-100">{{ orderActionsCount }}</p>
        </div>
        <div class="ui-stat-tile">
          <p class="ui-stat-label">{{ t("ownerHome.interactionRate") }}</p>
          <p class="ui-stat-value text-[var(--color-secondary)]">{{ interactionRateLabel }}</p>
        </div>
      </template>
    </div>

    <!-- Network error -->
    <div
      v-if="hasError && !loading"
      role="alert"
      class="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3"
    >
      <svg aria-hidden="true" viewBox="0 0 20 20" class="h-4 w-4 shrink-0 text-red-400/70" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-10.5a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 7a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-xs text-slate-400">{{ t("ownerHome.analyticsLoadError") }}</p>
      <button
        class="shrink-0 rounded-lg border border-slate-700 px-2.5 py-1 text-[11px] font-semibold text-slate-300 transition hover:border-slate-600"
        @click="hydrate(true)"
      >
        {{ t("common.retry") }}
      </button>
    </div>

    <!-- Empty state — new restaurant -->
    <div
      v-else-if="!hasError && !loading && !hasFunnelData && !topCategories.length"
      class="rounded-xl border border-slate-800/60 bg-slate-900/30 px-4 py-5 text-center space-y-1"
    >
      <AppIcon name="chart" class="mx-auto h-6 w-6 text-slate-600" />
      <p class="text-sm font-medium text-slate-400">{{ t("ownerHome.noAnalyticsData") }}</p>
      <p class="text-xs text-slate-600">{{ t("ownerHome.noAnalyticsDataHint") }}</p>
    </div>

    <!-- Conversion funnel -->
    <div v-if="hasFunnelData" class="ui-admin-subcard space-y-3">
      <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.funnelTitle") }}</p>
      <div class="space-y-2">
        <div v-for="(step, i) in funnelSteps" :key="step.key" class="funnel-step">
          <div class="flex items-center justify-between gap-2 text-sm">
            <span class="text-slate-300">{{ step.label }}</span>
            <div class="flex items-center gap-2 shrink-0">
              <span v-if="step.dropPct !== null" class="funnel-drop-badge">−{{ step.dropPct }}%</span>
              <span class="w-14 text-right tabular-nums font-semibold text-slate-100">{{ formatNumber(step.value) }}</span>
            </div>
          </div>
          <div class="mt-1.5 h-2 w-full rounded-full bg-slate-800">
            <div
              class="h-2 rounded-full transition-all duration-500"
              :class="step.barClass"
              :style="{ width: step.widthPct + '%' }"
            />
          </div>
          <p v-if="i < funnelSteps.length - 1 && step.convRate !== null" class="mt-0.5 text-right text-[10px] text-slate-500">
            {{ step.convRate }}% {{ t("ownerHome.funnelConvert") }}
          </p>
        </div>
      </div>
      <p v-if="funnelOverall !== null" class="border-t border-slate-800/60 pt-2 text-xs text-slate-500">
        {{ t("ownerHome.funnelOverall", { pct: funnelOverall }) }}
      </p>
    </div>

    <!-- Top categories + dishes -->
    <div class="grid gap-2 sm:grid-cols-2 sm:gap-3">
      <div class="ui-admin-subcard">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.topCategories") }}</p>
        <ul v-if="topCategories.length" class="mt-3 space-y-2 text-sm text-slate-200">
          <li v-for="item in topCategories" :key="item.category_slug" class="flex items-center justify-between gap-3">
            <span class="truncate">{{ resolveCategory(item.category_slug) }}</span>
            <span class="shrink-0 text-slate-400">{{ item.count }}</span>
          </li>
        </ul>
        <div v-else class="ui-empty-state mt-3 px-4 py-4 text-center">
          <AppIcon name="chart" class="mx-auto h-5 w-5 text-slate-500" />
          <p class="mt-2 text-sm text-slate-400">{{ t("ownerHome.noDataYet") }}</p>
        </div>
      </div>
      <div class="ui-admin-subcard">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">{{ t("ownerHome.topDishes") }}</p>
        <ul v-if="topDishes.length" class="mt-3 space-y-2 text-sm text-slate-200">
          <li v-for="item in topDishes" :key="item.dish_slug" class="flex items-center justify-between gap-3">
            <span class="truncate">{{ resolveDish(item.dish_slug) }}</span>
            <span class="shrink-0 text-slate-400">{{ item.count }}</span>
          </li>
        </ul>
        <div v-else class="ui-empty-state mt-3 px-4 py-4 text-center">
          <AppIcon name="menu" class="mx-auto h-5 w-5 text-slate-500" />
          <p class="mt-2 text-sm text-slate-400">{{ t("ownerHome.noDataYet") }}</p>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import AppIcon from "./AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";
import { bustCache, isFresh, readCache, writeCache } from "../lib/staleCache";
import { useToastStore } from "../stores/toast";

const { t, formatNumber } = useI18n();
const toast = useToastStore();

const PERIOD_OPTIONS = [7, 14, 30, 90];
const INSIGHTS_TTL_MS = 3 * 60 * 1000;

const props = defineProps({
  /** slug → name maps passed in from OwnerDashboardReadiness via the parent */
  categoryNameBySlug: { type: Object, default: () => ({}) },
  dishNameBySlug:     { type: Object, default: () => ({}) },
  /**
   * Global period in days, controlled by the parent. When this changes the
   * component re-fetches automatically. Defaults to 30 if not provided.
   */
  period:             { type: Number, default: 30 },
});

// ── Own loading state ─────────────────────────────────────────────────────────
const loading = ref(false);
const updating = ref(false);
const hasError = ref(false);
const exporting = ref(false);
// Internal period mirrors the prop; kept as a writable ref for backward compat
// (the period-selector buttons inside this component still work).
const internalPeriod = ref(props.period);

// ── Analytics data ────────────────────────────────────────────────────────────
const summary = ref({ counts: {}, top_categories: [], top_dishes: [], interaction_rate_pct: 0 });

// ── Emits — lets parent/siblings react to period changes or loaded data ────────
const emit = defineEmits(["data", "period-change", "loading-change", "updating-change"]);

// ── Slug → human-readable label ───────────────────────────────────────────────
// Uses the name map when available; falls back to title-casing the slug.
const humanizeSlug = (slug) =>
  String(slug || "")
    .replace(/[-_]+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

const resolveCategory = (slug) => props.categoryNameBySlug[slug] || humanizeSlug(slug);
const resolveDish     = (slug) => props.dishNameBySlug[slug]     || humanizeSlug(slug);

// ── Derived ───────────────────────────────────────────────────────────────────
const counts = computed(() => summary.value?.counts || {});
const topCategories = computed(() => (summary.value?.top_categories || []).slice(0, 6));
const topDishes = computed(() => (summary.value?.top_dishes || []).slice(0, 6));

const orderActionsCount = computed(
  () => Number(counts.value?.order_handoff_click || 0) + Number(counts.value?.checkout_click || 0)
);
const interactionRateLabel = computed(
  () => `${formatNumber(summary.value?.interaction_rate_pct || 0, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`
);

const funnelData = computed(() => summary.value?.funnel || null);
const funnelOverall = computed(() => funnelData.value?.overall_rate_pct ?? null);
const hasFunnelData = computed(() => funnelSteps.value.some((s) => s.value > 0));

const funnelSteps = computed(() => {
  const f = funnelData.value;
  const menuViews = f?.menu_views ?? Number(counts.value?.menu_view || 0);
  const cartViews = f?.cart_views ?? Number(counts.value?.cart_view || 0);
  const intents = f?.order_intents ?? orderActionsCount.value;
  const orders = f?.orders_placed ?? 0;

  const steps = [
    { key: "menu", label: t("ownerHome.funnelMenuViews"), value: menuViews, barClass: "bg-slate-400/70", convRate: f?.cart_rate_pct ?? null },
    { key: "cart", label: t("ownerHome.funnelCartViews"), value: cartViews, barClass: "bg-amber-400/70", convRate: f?.intent_rate_pct ?? null },
    { key: "intent", label: t("ownerHome.funnelOrderIntents"), value: intents, barClass: "bg-orange-400/70", convRate: f?.completion_rate_pct ?? null },
    { key: "orders", label: t("ownerHome.funnelOrdersPlaced"), value: orders, barClass: "bg-emerald-400/80", convRate: null },
  ];
  const maxVal = Math.max(...steps.map((s) => s.value), 1);
  return steps.map((step, i) => {
    const prev = i > 0 ? steps[i - 1].value : null;
    const dropped = prev !== null && prev > 0 ? Math.round(((prev - step.value) / prev) * 100) : null;
    return { ...step, widthPct: Math.max(Math.round((step.value / maxVal) * 100), step.value > 0 ? 2 : 0), dropPct: dropped };
  });
});

// ── Fetch (with stale-while-revalidate) ───────────────────────────────────────
let _abort = null;

const hydrate = async (force = false) => {
  _abort?.abort();
  const ctrl = new AbortController();
  _abort = ctrl;

  hasError.value = false;
  const cacheKey = `owner.insights.${internalPeriod.value}d`;
  if (force) bustCache(cacheKey);
  const cached = readCache(cacheKey);

  if (cached) {
    _apply(cached);
    if (isFresh(cacheKey, INSIGHTS_TTL_MS)) return;
    updating.value = true;
    emit("updating-change", true);
  } else {
    loading.value = true;
    emit("loading-change", true);
  }

  try {
    const { data } = await api.get("/owner/dashboard/", {
      params: { days: internalPeriod.value },
      signal: ctrl.signal,
      timeout: 8000,
    });
    if (ctrl.signal.aborted) return;
    _apply(data);
    writeCache(cacheKey, data);
    emit("data", data); // bubble up upgrade/revenue/reservations data to parent
  } catch (err) {
    if (err.code === "ERR_CANCELED" || err.name === "AbortError" || ctrl.signal.aborted) return;
    // Fallback to analytics-only endpoint
    try {
      const { data } = await api.get("/analytics/summary/", { params: { days: internalPeriod.value }, timeout: 5000 });
      if (data?.analytics_summary) summary.value = data.analytics_summary;
      else if (data?.counts) summary.value = data;
    } catch {
      if (!cached) hasError.value = true;
    }
  } finally {
    if (!ctrl.signal.aborted) {
      loading.value = false;
      updating.value = false;
      emit("loading-change", false);
      emit("updating-change", false);
    }
  }
};

const _apply = (data) => {
  if (data?.analytics_summary) summary.value = data.analytics_summary;
};

const setPeriod = (d) => {
  if (d === internalPeriod.value) return;
  internalPeriod.value = d;
  emit("period-change", d);
  void hydrate();
};

const exportCsv = async () => {
  if (exporting.value) return;
  exporting.value = true;
  try {
    const response = await api.get("/owner/analytics/export/", {
      params: { days: internalPeriod.value },
      responseType: "blob",
      timeout: 15000,
    });
    const url = URL.createObjectURL(new Blob([response.data], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `analytics_${period.value}d.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    toast.show(t("ownerHome.exportFailed"), "error");
  } finally {
    exporting.value = false;
  }
};

// ── Watch prop changes — when parent changes the global period, sync & refetch ─
watch(() => props.period, (newPeriod) => {
  if (newPeriod !== internalPeriod.value) {
    internalPeriod.value = newPeriod;
    void hydrate();
  }
});

// ── Public API so parent can trigger a force-refresh ─────────────────────────
defineExpose({ hydrate, period: internalPeriod });

onMounted(() => void hydrate());
</script>

<style scoped>
.owner-insights-icon { width: 1rem; height: 1rem; color: var(--color-secondary); }
.funnel-drop-badge {
  display: inline-flex; align-items: center; padding: 0.05rem 0.35rem;
  border-radius: 0.3rem; font-size: 0.68rem; font-weight: 600;
  background: rgba(239,68,68,0.12); color: #f87171; letter-spacing: 0.02em;
}
</style>
