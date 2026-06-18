<template>
  <div class="ui-page-shell space-y-4 ui-safe-bottom">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal space-y-3 px-4 py-4 sm:px-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t("zReport.kicker") }}</p>
          <h1 class="ui-display text-2xl font-bold tracking-tight text-white sm:text-3xl">{{ t("zReport.title") }}</h1>
          <p class="ui-subtle">{{ t("zReport.description") }}</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <!-- Date picker -->
          <label class="flex items-center gap-1.5 text-xs text-slate-400">
            <span>{{ t("zReport.date") }}</span>
            <input
              v-model="selectedDate"
              type="date"
              :max="todayIso"
              class="ui-input py-1 text-xs"
              :aria-label="t('zReport.date')"
              @change="fetchReport"
            />
          </label>
          <button
            type="button"
            class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
            :disabled="loading"
            :aria-label="t('common.refresh')"
            @click="fetchReport"
          >
            <AppIcon name="refresh" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ loading ? t("common.loading") : t("common.refresh") }}
          </button>
          <!-- CSV export -->
          <button
            type="button"
            class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
            :disabled="exporting || !report"
            :aria-label="t('zReport.downloadCsv')"
            @click="downloadCsv"
          >
            <AppIcon name="download" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ exporting ? t("common.loading") : t("zReport.downloadCsv") }}
          </button>
          <!-- Print -->
          <button
            type="button"
            class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
            :disabled="!report"
            :aria-label="t('zReport.print')"
            @click="printReport"
          >
            <AppIcon name="print" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t("zReport.print") }}
          </button>
        </div>
      </div>
    </header>

    <!-- Error -->
    <div v-if="error" role="alert" class="mx-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      {{ error }}
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !report" class="space-y-3 px-4" aria-busy="true" :aria-label="t('common.loading')">
      <div class="ui-skeleton h-24 rounded-xl" />
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div v-for="i in 6" :key="i" class="ui-skeleton h-20 rounded-xl" />
      </div>
    </div>

    <!-- Report -->
    <div v-if="report" id="z-report-print-target" class="space-y-4 px-4">

      <!-- Service-day window banner -->
      <div class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 px-4 py-3 space-y-1 print:border-slate-300 print:bg-white">
        <div class="flex flex-wrap items-center gap-3">
          <span class="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-amber-300 print:border-amber-300 print:bg-amber-50 print:text-amber-700">
            {{ t("zReport.serviceDay") }}
          </span>
          <span class="font-semibold text-white text-sm print:text-black">{{ report.window.service_day }}</span>
          <span v-if="report.window.cutover_hour > 0" class="text-xs text-slate-400 print:text-slate-600">
            {{ t("zReport.cutoverHour", { h: report.window.cutover_hour }) }}
          </span>
        </div>
        <p class="text-[11px] text-slate-500 print:text-slate-600">
          {{ formatWindowTime(report.window.start) }} &ndash; {{ formatWindowTime(report.window.end) }}
        </p>
      </div>

      <!-- Money KPI grid -->
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 print:grid-cols-3">
        <!-- Collected cash -->
        <div class="ui-admin-subcard ui-reveal space-y-1.5 p-3 print:border print:border-slate-300 print:bg-white print:shadow-none">
          <p class="ui-stat-label print:text-slate-500">{{ t("zReport.collectedCash") }}</p>
          <p class="text-xl font-bold tabular-nums text-emerald-300 print:text-emerald-700">{{ fmtMoney(report.collected.cash) }}</p>
        </div>
        <!-- Collected wallet -->
        <div class="ui-admin-subcard ui-reveal space-y-1.5 p-3 print:border print:border-slate-300 print:bg-white print:shadow-none">
          <p class="ui-stat-label print:text-slate-500">{{ t("zReport.collectedWallet") }}</p>
          <p class="text-xl font-bold tabular-nums text-sky-300 print:text-sky-700">{{ fmtMoney(report.collected.wallet) }}</p>
        </div>
        <!-- Collected total -->
        <div class="ui-admin-subcard ui-reveal space-y-1.5 p-3 border-[var(--color-secondary)]/30 print:border print:border-slate-300 print:bg-white print:shadow-none">
          <p class="ui-stat-label print:text-slate-500">{{ t("zReport.collectedTotal") }}</p>
          <p class="text-xl font-bold tabular-nums text-[var(--color-secondary)] print:text-slate-800">{{ fmtMoney(report.collected.total) }}</p>
        </div>
        <!-- Tips -->
        <div class="ui-admin-subcard ui-reveal space-y-1.5 p-3 print:border print:border-slate-300 print:bg-white print:shadow-none">
          <p class="ui-stat-label print:text-slate-500">{{ t("zReport.tips") }}</p>
          <p class="text-xl font-bold tabular-nums text-amber-300 print:text-amber-700">{{ fmtMoney(report.tips.total) }}</p>
        </div>
        <!-- Refunds -->
        <div class="ui-admin-subcard ui-reveal space-y-1.5 p-3 print:border print:border-slate-300 print:bg-white print:shadow-none">
          <p class="ui-stat-label print:text-slate-500">{{ t("zReport.refunds") }}</p>
          <p class="text-xl font-bold tabular-nums text-red-400 print:text-red-700">
            -{{ fmtMoney(report.refunds.total) }}
            <span class="text-[11px] font-normal text-slate-500 print:text-slate-600">({{ report.refunds.count }})</span>
          </p>
          <p class="text-[10px] text-slate-600 print:text-slate-400">{{ t("zReport.refundsBasis") }}</p>
        </div>
        <!-- Net cash position -->
        <div class="ui-admin-subcard ui-reveal space-y-1.5 p-3 print:border print:border-slate-300 print:bg-white print:shadow-none">
          <p class="ui-stat-label print:text-slate-500">{{ t("zReport.netCash") }}</p>
          <p class="text-xl font-bold tabular-nums text-white print:text-black">{{ fmtMoney(report.net_cash_position) }}</p>
        </div>
      </div>

      <!-- Reconciliation line -->
      <div class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 px-4 py-3 flex flex-wrap items-center justify-between gap-3 print:border-slate-300 print:bg-white">
        <p class="text-sm font-semibold text-slate-200 print:text-black">{{ t("zReport.netLabel") }}</p>
        <p class="text-2xl font-bold tabular-nums text-[var(--color-secondary)] print:text-slate-800">{{ fmtMoney(report.net) }}</p>
      </div>

      <!-- Voids -->
      <div class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 print:border-slate-300 print:bg-white">
        <button
          type="button"
          class="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-200 print:pointer-events-none print:text-black"
          :aria-expanded="voidsExpanded"
          @click="voidsExpanded = !voidsExpanded"
        >
          <span>{{ t("zReport.voidsTitle") }} <span class="ms-1.5 text-xs font-normal text-slate-500">({{ report.voids.count }})</span></span>
          <span class="text-xs text-slate-500 print:hidden">{{ fmtMoney(report.voids.total) }}</span>
          <AppIcon v-if="report.voids.count > 0" :name="voidsExpanded ? 'chevronUp' : 'chevronDown'" class="h-4 w-4 shrink-0 text-slate-500 ms-2 print:hidden" aria-hidden="true" />
        </button>
        <Transition name="ui-fade">
          <div v-if="voidsExpanded && report.voids.items.length" class="border-t border-slate-800 px-4 pb-3 print:border-slate-300">
            <table class="w-full text-xs mt-2">
              <thead>
                <tr class="text-slate-500 text-left border-b border-slate-800 print:border-slate-300">
                  <th class="py-1.5 pe-2 font-medium">{{ t("zReport.colOrder") }}</th>
                  <th class="py-1.5 pe-2 font-medium">{{ t("zReport.colItem") }}</th>
                  <th class="py-1.5 pe-2 font-medium text-center">{{ t("zReport.colQty") }}</th>
                  <th class="py-1.5 pe-2 font-medium text-end">{{ t("zReport.colTotal") }}</th>
                  <th class="py-1.5 font-medium">{{ t("zReport.colReason") }}</th>
                  <th class="py-1.5 font-medium">{{ t("zReport.colVoidedBy") }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, idx) in report.voids.items"
                  :key="idx"
                  class="border-b border-slate-800/50 last:border-0 print:border-slate-200"
                >
                  <td class="py-1.5 pe-2 text-slate-400 print:text-slate-600">{{ item.order_number }}</td>
                  <td class="py-1.5 pe-2 text-slate-200 print:text-black">{{ item.dish_name }}</td>
                  <td class="py-1.5 pe-2 text-center text-slate-400 print:text-slate-600">{{ item.qty }}</td>
                  <td class="py-1.5 pe-2 text-end font-semibold tabular-nums text-red-400 print:text-red-700">{{ fmtMoney(item.line_total) }}</td>
                  <td class="py-1.5 pe-2 text-slate-400 italic print:text-slate-600">{{ item.reason || t("zReport.noReason") }}</td>
                  <td class="py-1.5 text-slate-400 print:text-slate-600">{{ item.voided_by || t("zReport.unknown") }}</td>
                </tr>
              </tbody>
            </table>
            <p class="mt-1.5 text-[11px] text-slate-500 print:text-slate-400">{{ t("zReport.voidsTotal") }}: <span class="font-semibold">{{ fmtMoney(report.voids.total) }}</span></p>
          </div>
          <p v-else-if="voidsExpanded && !report.voids.items.length" class="border-t border-slate-800 px-4 py-2 text-xs text-slate-500 print:border-slate-300 print:text-slate-400">
            {{ t("zReport.noVoids") }}
          </p>
        </Transition>
      </div>

      <!-- By-staff table -->
      <div v-if="report.by_staff.length" class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 px-4 py-3 print:border-slate-300 print:bg-white">
        <p class="mb-2 text-sm font-semibold text-slate-200 print:text-black">{{ t("zReport.byStaff") }}</p>
        <table class="w-full text-xs">
          <thead>
            <tr class="text-slate-500 text-left border-b border-slate-800 print:border-slate-300">
              <th class="py-1.5 pe-2 font-medium">{{ t("zReport.staffName") }}</th>
              <th class="py-1.5 pe-2 font-medium text-center">{{ t("zReport.staffOrders") }}</th>
              <th class="py-1.5 pe-2 font-medium text-end">{{ t("zReport.staffCash") }}</th>
              <th class="py-1.5 font-medium text-end">{{ t("zReport.staffWallet") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in report.by_staff"
              :key="row.name"
              class="border-b border-slate-800/50 last:border-0 print:border-slate-200"
            >
              <td class="py-1.5 pe-2 font-medium text-slate-200 print:text-black">{{ row.name }}</td>
              <td class="py-1.5 pe-2 text-center text-slate-400 print:text-slate-600">{{ row.orders }}</td>
              <td class="py-1.5 pe-2 text-end tabular-nums text-emerald-300 print:text-emerald-700">{{ fmtMoney(row.collected_cash) }}</td>
              <td class="py-1.5 text-end tabular-nums text-sky-300 print:text-sky-700">{{ fmtMoney(row.collected_wallet) }}</td>
            </tr>
          </tbody>
        </table>
        <p class="mt-1.5 text-[10px] text-slate-600 print:text-slate-400">{{ t("zReport.byStaffNote") }}</p>
      </div>
      <p v-else-if="report" class="px-4 text-xs text-slate-500">{{ t("zReport.noStaffData") }}</p>

      <!-- Food-cost card -->
      <div v-if="report?.food_cost?.total" class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 px-4 py-3 print:border-slate-300 print:bg-white">
        <p class="mb-2 text-sm font-semibold text-slate-200 print:text-black">{{ t("zReport.foodCostTitle") }}</p>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500 print:text-slate-400">{{ t("zReport.foodCostTotal") }}</p>
            <p class="text-lg font-bold tabular-nums text-orange-300 print:text-orange-700">{{ fmtMoney(report.food_cost.total) }}</p>
          </div>
          <div v-if="report.food_cost.food_cost_pct">
            <p class="text-[10px] uppercase tracking-wider text-slate-500 print:text-slate-400">{{ t("zReport.foodCostPct") }}</p>
            <p class="text-lg font-bold tabular-nums text-orange-300 print:text-orange-700">{{ report.food_cost.food_cost_pct }}%</p>
          </div>
        </div>
        <p class="mt-1.5 text-[10px] text-slate-600 print:text-slate-400">{{ t("zReport.foodCostNote") }}</p>
      </div>

      <!-- Labor section -->
      <div v-if="report?.labor" class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 print:border-slate-300 print:bg-white">
        <button
          type="button"
          class="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-200 print:pointer-events-none print:text-black"
          :aria-expanded="laborExpanded"
          @click="laborExpanded = !laborExpanded"
        >
          <span>{{ t("zReport.laborTitle") }} <span class="ms-1.5 text-xs font-normal text-slate-500">({{ report.labor.shifts?.length ?? 0 }})</span></span>
          <span class="text-xs text-slate-500 print:hidden">{{ report.labor.total_labor_cost ? fmtMoney(report.labor.total_labor_cost) : (report.labor.total_hours + 'h') }}</span>
          <AppIcon :name="laborExpanded ? 'chevronUp' : 'chevronDown'" class="h-4 w-4 shrink-0 text-slate-500 ms-2 print:hidden" aria-hidden="true" />
        </button>
        <Transition name="ui-fade">
          <div v-if="laborExpanded" class="border-t border-slate-800 px-4 pb-3 print:border-slate-300">
            <!-- Labor KPIs -->
            <div class="mt-2 grid grid-cols-3 gap-3 pb-2">
              <div>
                <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("zReport.laborTotalHours") }}</p>
                <p class="text-base font-bold tabular-nums text-slate-200">{{ report.labor.total_hours }}h</p>
              </div>
              <div v-if="report.labor.total_labor_cost">
                <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("zReport.laborTotalCost") }}</p>
                <p class="text-base font-bold tabular-nums text-slate-200">{{ fmtMoney(report.labor.total_labor_cost) }}</p>
              </div>
              <div v-if="report.labor.labor_pct">
                <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("zReport.laborPct") }}</p>
                <p class="text-base font-bold tabular-nums text-slate-200">{{ report.labor.labor_pct }}%</p>
              </div>
            </div>
            <!-- Shift list -->
            <p v-if="!report.labor.shifts?.length" class="text-xs text-slate-500">{{ t("zReport.laborNoShifts") }}</p>
            <table v-else class="w-full text-xs mt-1">
              <thead>
                <tr class="border-b border-slate-800 text-left text-slate-500 print:border-slate-300">
                  <th class="py-1.5 pe-2 font-medium">{{ t("zReport.staffName") }}</th>
                  <th class="py-1.5 pe-2 font-medium text-center">{{ t("zReport.laborTotalHours") }}</th>
                  <th class="py-1.5 font-medium text-end">{{ t("zReport.laborTotalCost") }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(sh, idx) in report.labor.shifts"
                  :key="idx"
                  class="border-b border-slate-800/50 last:border-0 print:border-slate-200"
                >
                  <td class="py-1.5 pe-2 font-medium text-slate-200 print:text-black">{{ sh.user_name }}</td>
                  <td class="py-1.5 pe-2 text-center tabular-nums text-slate-400">
                    {{ sh.hours != null ? sh.hours + 'h' : t("zReport.laborStillOpen") }}
                  </td>
                  <td class="py-1.5 text-end tabular-nums text-slate-400">
                    {{ sh.labor_cost ? fmtMoney(sh.labor_cost) : '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Transition>
      </div>

    </div>

    <!-- Empty state when no report yet and not loading -->
    <div v-if="!report && !loading && !error" class="ui-empty-state mx-4 rounded-xl py-12 text-center print:hidden">
      <p class="text-slate-500">{{ t("zReport.noData") }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import { useTenantStore } from "../stores/tenant";
import api from "../lib/api";

defineOptions({ name: "OwnerZReport" });

const { t } = useI18n();
const toast = useToastStore();
const tenant = useTenantStore();

const report = ref(null);
const loading = ref(false);
const exporting = ref(false);
const error = ref("");
const voidsExpanded = ref(true);
const laborExpanded = ref(true);

// Default date = today in ISO format
const todayIso = computed(() => new Date().toISOString().slice(0, 10));
const selectedDate = ref(""); // empty = current service day

const currency = computed(() => tenant.resolvedMeta?.profile?.currency || "MAD");

const fmtMoney = (val) => {
  const n = Number(val) || 0;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency.value,
      minimumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${currency.value} ${n.toFixed(2)}`;
  }
};

const formatWindowTime = (iso) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const fetchReport = async () => {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    const params = {};
    if (selectedDate.value) params.date = selectedDate.value;
    const { data } = await api.get("/owner/z-report/", { params });
    report.value = data;
    voidsExpanded.value = true;
  } catch (err) {
    error.value = err?.response?.data?.detail || t("zReport.loadFailed");
  } finally {
    loading.value = false;
  }
};

const downloadCsv = async () => {
  if (exporting.value || !report.value) return;
  exporting.value = true;
  try {
    const params = { format: "csv" };
    if (selectedDate.value) params.date = selectedDate.value;
    const resp = await api.get("/owner/z-report.csv", {
      params,
      responseType: "blob",
      headers: { Accept: "text/csv" },
    });
    const url = URL.createObjectURL(resp.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `z-report-${report.value.window.service_day}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch {
    toast.show(t("zReport.exportFailed"), "error");
  } finally {
    exporting.value = false;
  }
};

const printReport = () => {
  window.print();
};

onMounted(fetchReport);
</script>

<style>
@media print {
  /* Hide the entire owner layout chrome — only show the z-report */
  .ui-header,
  .ui-shell > *:not(main),
  .ui-hero-ribbon .flex.flex-wrap.items-center.gap-2,
  button[aria-label*="Refresh"],
  button[aria-label*="Download"],
  button[aria-label*="Print"],
  .print\:hidden {
    display: none !important;
  }
  body {
    background: white !important;
    color: black !important;
    font-size: 11pt;
  }
  #z-report-print-target {
    padding: 0 !important;
  }
  .ui-page-shell {
    padding: 0 !important;
  }
  /* A4 dimensions */
  @page {
    size: A4 portrait;
    margin: 18mm 15mm;
  }
}
</style>
