<template>
  <!--
    Fulfillment split widget — pickup / delivery / table.
    Shows a stacked percentage bar (CSS only, no chart library) and a
    3-row breakdown table with counts and revenue.

    Props:
      breakdown  Object   — { pickup: {count, revenue, count_pct}, delivery: …, table: … }
      loading    Boolean  — show skeleton
      currency   String   — ISO 4217 currency code for revenue formatting
  -->
  <div class="space-y-3">
    <p class="ui-kicker">
      {{ t("ownerHome.fulfillmentTitle") }}
    </p>

    <!-- Skeleton -->
    <template v-if="loading">
      <div class="ui-skeleton h-3 w-full" aria-hidden="true" />
      <div class="space-y-2 pt-0.5">
        <div v-for="i in 3" :key="i" class="flex items-center justify-between gap-3">
          <div class="h-2.5 w-16 animate-pulse rounded bg-slate-800/60" :style="{ animationDelay: `${i * 60}ms` }" />
          <div class="h-2.5 w-10 animate-pulse rounded bg-slate-700/60" :style="{ animationDelay: `${i * 60 + 30}ms` }" />
        </div>
      </div>
    </template>

    <!-- No data yet -->
    <div
      v-else-if="!rows.length"
      class="ui-empty-state p-4 text-center"
    >
      <p class="text-xs font-medium text-slate-300">{{ t("ownerHome.noOrdersYet") }}</p>
    </div>

    <template v-else>
      <!-- Stacked percentage bar -->
      <div
        class="flex h-3 w-full overflow-hidden rounded-full"
        role="img"
        :aria-label="stackedBarLabel"
      >
        <div
          v-for="row in rows"
          :key="row.key"
          :class="row.barClass"
          :style="{ width: `${row.pct}%`, transition: 'width var(--motion-slow) var(--ease-fluid)' }"
          :title="`${row.label}: ${row.pct}%`"
        />
      </div>

      <!-- Legend rows -->
      <div class="space-y-1.5">
        <div
          v-for="(row, index) in rows"
          :key="row.key"
          class="ui-reveal flex min-h-[1.75rem] items-center gap-2 text-xs"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <!-- Color dot -->
          <span class="h-2 w-2 shrink-0 rounded-full" :class="row.dotClass" aria-hidden="true" />

          <!-- Label -->
          <span class="min-w-0 flex-1 truncate font-medium text-slate-200">{{ row.label }}</span>

          <!-- Count + pct -->
          <span class="shrink-0 tabular-nums text-slate-400">
            {{ row.count }} <span class="text-slate-600">({{ row.pct }}%)</span>
          </span>

          <!-- Revenue -->
          <span class="w-20 shrink-0 text-end tabular-nums text-[var(--color-secondary)]">
            {{ fmtRevenue(row.revenue) }}
          </span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";

const { t, formatNumber } = useI18n();

const props = defineProps({
  breakdown: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  currency: { type: String, default: null },
});

// ── Style config per fulfillment type ─────────────────────────────────────────
const STYLE = {
  pickup: {
    barClass: "bg-[var(--color-secondary)]/80",
    dotClass: "bg-[var(--color-secondary)]",
    labelKey: "ownerHome.fulfillmentPickup",
  },
  delivery: {
    barClass: "bg-sky-500/80",
    dotClass: "bg-sky-400",
    labelKey: "ownerHome.fulfillmentDelivery",
  },
  table: {
    barClass: "bg-violet-500/80",
    dotClass: "bg-violet-400",
    labelKey: "ownerHome.fulfillmentTable",
  },
};

// ── Build sorted rows from the backend breakdown object ───────────────────────
const rows = computed(() => {
  const bd = props.breakdown || {};
  const entries = Object.entries(bd)
    .map(([key, data]) => ({
      key,
      label: t(STYLE[key]?.labelKey || "ownerHome.fulfillmentPickup"),
      count: data.count || 0,
      revenue: data.revenue || 0,
      pct: data.count_pct || 0,
      barClass: STYLE[key]?.barClass || "bg-slate-500/70",
      dotClass: STYLE[key]?.dotClass || "bg-slate-400",
    }))
    .filter((r) => r.count > 0)
    .sort((a, b) => b.count - a.count);
  return entries;
});

// Accessible label for the stacked bar
const stackedBarLabel = computed(() =>
  rows.value.map((r) => `${r.label} ${r.pct}%`).join(", ")
);

// Revenue formatter — same pattern as OwnerDashboardRevenue
const fmtRevenue = (amount) => {
  const n = Number(amount) || 0;
  if (n === 0) return "—";
  if (!props.currency) return `${Math.round(n)}`;
  try { return formatNumber(n, { style: "currency", currency: props.currency, maximumFractionDigits: 0 }); }
  catch { return `${Math.round(n)}`; }
};
</script>
