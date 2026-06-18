<template>
  <article class="ui-panel space-y-4 p-4 sm:p-5" :aria-busy="loading" aria-labelledby="repeat-analytics-heading">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 id="repeat-analytics-heading" class="ui-subheading text-sm font-semibold uppercase tracking-widest text-slate-400">
        {{ t("repeatAnalytics.title") }}
      </h3>
      <span class="rounded-full bg-slate-800/60 px-2 py-0.5 text-[10px] font-semibold text-slate-500">{{ period }}d</span>
    </div>

    <!-- Skeleton -->
    <div v-if="loading" class="grid grid-cols-3 gap-2.5" aria-hidden="true">
      <div v-for="i in 3" :key="i" class="ui-skeleton h-24 rounded-xl" />
    </div>

    <!-- No data -->
    <p v-else-if="!data" class="py-4 text-center text-xs text-slate-500">
      {{ t("repeatAnalytics.noData") }}
    </p>

    <template v-else>
      <!-- 3 metric cards -->
      <div class="grid grid-cols-3 gap-2.5">
        <!-- Repeat rate -->
        <div class="ui-admin-subcard flex flex-col gap-1 p-3 text-center">
          <p class="ui-stat-label">{{ t("repeatAnalytics.repeatRate") }}</p>
          <p
            class="ui-stat-value !mt-0 text-2xl font-bold tabular-nums"
            :class="data.repeat_rate >= 25 ? 'text-emerald-400' : data.repeat_rate >= 10 ? 'text-amber-400' : 'text-slate-300'"
          >{{ data.repeat_rate }}%</p>
          <p class="mt-auto text-[10px] leading-tight text-slate-500">
            {{ data.repeat_customers }}/{{ data.unique_paying }}
          </p>
        </div>

        <!-- New customers -->
        <div class="ui-admin-subcard flex flex-col gap-1 p-3 text-center">
          <p class="ui-stat-label">{{ t("repeatAnalytics.newCustomers") }}</p>
          <p class="ui-stat-value !mt-0 text-2xl font-bold tabular-nums text-sky-400">{{ data.new_customers }}</p>
          <p class="mt-auto text-[10px] tabular-nums text-slate-500">{{ fmtRevenue(data.new_revenue) }}</p>
        </div>

        <!-- Returning customers -->
        <div class="ui-admin-subcard flex flex-col gap-1 p-3 text-center">
          <p class="ui-stat-label">{{ t("repeatAnalytics.returning") }}</p>
          <p class="ui-stat-value !mt-0 text-2xl font-bold tabular-nums text-violet-400">{{ data.returning_customers }}</p>
          <p class="mt-auto text-[10px] tabular-nums text-slate-500">{{ fmtRevenue(data.returning_revenue) }}</p>
        </div>
      </div>

      <!-- Revenue split bar -->
      <div v-if="totalRevenue > 0" class="space-y-1.5">
        <p class="text-[10px] font-medium uppercase tracking-wider text-slate-500">
          {{ t("repeatAnalytics.revenueSplit") }}
        </p>
        <div class="flex h-2 overflow-hidden rounded-full bg-slate-800" role="img" :aria-label="`${newPct}% new, ${returningPct}% returning`">
          <div class="bg-sky-500 transition-all duration-500" :style="{ width: newPct + '%' }" />
          <div class="bg-violet-500 transition-all duration-500" :style="{ width: returningPct + '%' }" />
        </div>
        <div class="flex justify-between text-[10px] text-slate-500">
          <span>{{ t("repeatAnalytics.newLabel") }} {{ newPct }}%</span>
          <span>{{ returningPct }}% {{ t("repeatAnalytics.returning") }}</span>
        </div>
      </div>
    </template>
  </article>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import api from "../lib/api";
import { useI18n } from "../composables/useI18n";
import { useTenantStore } from "../stores/tenant";

defineOptions({ name: "RepeatAnalyticsWidget" });

const props = defineProps({
  period: { type: Number, default: 30 },
});

const { t, formatNumber } = useI18n();
const tenant = useTenantStore();

const loading = ref(true);
const data = ref(null);

const currency = computed(() => tenant.resolvedMeta?.profile?.currency ?? "MAD");

const fmtRevenue = (val) => {
  const n = Number(val) || 0;
  try {
    return formatNumber(n, { style: "currency", currency: currency.value, maximumFractionDigits: 0 });
  } catch (e) { void e; }
  return `${currency.value} ${Math.round(n)}`;
};

const totalRevenue = computed(() => Number(data.value?.total_revenue) || 0);
const newPct = computed(() => {
  if (!totalRevenue.value) return 0;
  return Math.round((Number(data.value?.new_revenue || 0) / totalRevenue.value) * 100);
});
const returningPct = computed(() => {
  if (!totalRevenue.value) return 0;
  return 100 - newPct.value;
});

const load = async () => {
  loading.value = true;
  data.value = null;
  try {
    const resp = await api.get("/owner/repeat-analytics/", { params: { days: props.period } });
    data.value = resp.data?.unique_paying > 0 ? resp.data : null;
  } catch { void 0; }
  finally {
    loading.value = false;
  }
};

watch(() => props.period, load, { immediate: true });
</script>
