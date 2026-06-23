<template>
  <div class="ui-page-shell space-y-4 ui-safe-bottom">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal space-y-3 px-4 py-4 sm:px-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <p class="ui-kicker">{{ t("shiftClose.kicker") }}</p>
          <h1 class="ui-display text-2xl font-bold tracking-tight text-white sm:text-3xl">
            {{ t("shiftClose.title") }}
          </h1>
          <p class="ui-subtle">{{ t("shiftClose.description") }}</p>
        </div>
        <RouterLink
          :to="{ name: 'owner-home' }"
          class="ui-btn-outline inline-flex items-center gap-1.5 px-3 py-1.5 text-sm"
        >
          <AppIcon name="arrowLeft" class="h-3.5 w-3.5 rtl:scale-x-[-1]" aria-hidden="true" />
          {{ t("shiftClose.backToHome") }}
        </RouterLink>
      </div>
    </header>

    <!-- Error -->
    <div v-if="error" role="alert" class="mx-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      {{ error }}
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !report && !drawer" class="space-y-3 px-4" aria-busy="true">
      <div class="ui-skeleton h-32 rounded-xl" />
      <div class="ui-skeleton h-28 rounded-xl" />
    </div>

    <div
      v-else
      id="shift-close-print-target"
      class="space-y-4 px-4"
    >

      <!-- ── Cash drawer reconciliation ─────────────────────────────────────── -->
      <section class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 p-4 space-y-4 print:border-slate-300 print:bg-white">
        <h2 class="text-sm font-semibold text-slate-200 print:text-black">{{ t("shiftClose.cashSection") }}</h2>

        <!-- Closed session summary -->
        <template v-if="closedDrawer">
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("cashDrawer.openingFloat") }}</p>
              <p class="text-lg font-bold tabular-nums text-slate-200 print:text-black">{{ fmtMoney(closedDrawer.opening_float) }}</p>
            </div>
            <div>
              <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("cashDrawer.expectedTotal") }}</p>
              <p class="text-lg font-bold tabular-nums text-slate-200 print:text-black">{{ fmtMoney(closedDrawer.expected_total) }}</p>
            </div>
            <div>
              <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("cashDrawer.countedTotal") }}</p>
              <p class="text-lg font-bold tabular-nums text-slate-200 print:text-black">{{ fmtMoney(closedDrawer.counted_total) }}</p>
            </div>
          </div>
          <!-- Over / short badge -->
          <div
            class="flex items-center gap-3 rounded-xl border px-4 py-3"
            :class="overShortClass"
          >
            <span class="text-xl font-bold tabular-nums">{{ overShortLabel }}</span>
            <span class="text-sm font-semibold">{{ t("shiftClose.overShortLabel") }}</span>
          </div>
        </template>

        <!-- Open session — prompt close first -->
        <template v-else-if="openDrawer">
          <div class="rounded-xl border border-amber-500/30 bg-amber-500/8 px-4 py-3 space-y-3">
            <p class="text-sm font-semibold text-amber-200">{{ t("cashDrawer.statusOpen") }}</p>
            <p class="text-xs text-slate-400">{{ t("cashDrawer.blindCountHint") }}</p>
            <div class="flex items-end gap-3">
              <div class="flex-1">
                <label class="mb-1 block text-xs text-slate-400">{{ t("cashDrawer.countedTotal") }}</label>
                <input
                  v-model="countedInput"
                  type="number"
                  min="0"
                  step="0.01"
                  class="ui-input w-full text-sm"
                  :placeholder="`0.00`"
                  :disabled="closing"
                />
              </div>
              <button
                type="button"
                class="ui-btn-primary shrink-0 px-4 py-2 text-sm"
                :disabled="closing || !countedInput"
                @click="closeDrawerNow"
              >
                <svg v-if="closing" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin inline me-1"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
                {{ closing ? t("common.loading") : t("cashDrawer.submitClose") }}
              </button>
            </div>
          </div>
        </template>

        <!-- No drawer session -->
        <p v-else class="text-sm text-slate-500">{{ t("shiftClose.noDrawer") }}</p>
      </section>

      <!-- ── Pay-in / pay-out movements ───────────────────────────────────────── -->
      <section
        v-if="drawerTransactions.length"
        class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 p-4 print:border-slate-300 print:bg-white"
      >
        <h2 class="mb-2 text-sm font-semibold text-slate-200 print:text-black">{{ t("cashDrawer.transactions") }}</h2>
        <table class="w-full text-xs">
          <thead>
            <tr class="border-b border-slate-800 text-left text-slate-500 print:border-slate-300">
              <th class="py-1.5 pe-2 font-medium">{{ t("cashDrawer.amount") }}</th>
              <th class="py-1.5 pe-2 font-medium">{{ t("cashDrawer.reason") }}</th>
              <th class="py-1.5 font-medium text-end">{{ t("zReport.voidAt") }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="tx in drawerTransactions"
              :key="tx.id"
              class="border-b border-slate-800/50 last:border-0 print:border-slate-200"
            >
              <td
                class="py-1.5 pe-2 font-semibold tabular-nums"
                :class="tx.kind === 'pay_in' ? 'text-emerald-300 print:text-emerald-700' : 'text-red-400 print:text-red-700'"
              >
                {{ tx.kind === 'pay_in' ? '+' : '-' }}{{ fmtMoney(tx.amount) }}
                <span class="ms-1 text-[10px] font-normal text-slate-500">{{ tx.kind === 'pay_in' ? t('cashDrawer.payIn') : t('cashDrawer.payOut') }}</span>
              </td>
              <td class="py-1.5 pe-2 text-slate-400 italic print:text-slate-600">{{ tx.reason || '—' }}</td>
              <td class="py-1.5 text-end tabular-nums text-slate-500">{{ fmtTime(tx.at) }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- ── Z-report summary card ─────────────────────────────────────────────── -->
      <section v-if="report" class="ui-workspace-stage ui-reveal rounded-xl border border-slate-700/50 p-4 space-y-3 print:border-slate-300 print:bg-white">
        <h2 class="text-sm font-semibold text-slate-200 print:text-black">{{ t("shiftClose.summarySection") }}</h2>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("shiftClose.ordersLabel") }}</p>
            <p class="text-lg font-bold tabular-nums text-slate-200 print:text-black">{{ report.collected?.total !== undefined ? report.collected_count ?? '—' : '—' }}</p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("shiftClose.revenueLabel") }}</p>
            <p class="text-lg font-bold tabular-nums text-[var(--color-secondary)] print:text-slate-800">{{ fmtMoney(report.collected?.total) }}</p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("shiftClose.tipsTotalLabel") }}</p>
            <p class="text-lg font-bold tabular-nums text-amber-300 print:text-amber-700">{{ fmtMoney(report.tips?.total) }}</p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("shiftClose.collectedCashLabel") }}</p>
            <p class="text-lg font-bold tabular-nums text-emerald-300 print:text-emerald-700">{{ fmtMoney(report.collected?.cash) }}</p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("shiftClose.collectedWalletLabel") }}</p>
            <p class="text-lg font-bold tabular-nums text-sky-300 print:text-sky-700">{{ fmtMoney(report.collected?.wallet) }}</p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("shiftClose.voidsCountLabel") }}</p>
            <p class="text-lg font-bold tabular-nums text-slate-200 print:text-black">{{ report.voids?.count ?? 0 }}</p>
          </div>
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t("shiftClose.voidsTotalLabel") }}</p>
            <p class="text-lg font-bold tabular-nums text-red-400 print:text-red-700">{{ fmtMoney(report.voids?.total) }}</p>
          </div>
        </div>
      </section>

      <!-- ── Actions ───────────────────────────────────────────────────────────── -->
      <div class="flex flex-wrap gap-3 print:hidden">
        <button
          type="button"
          class="ui-btn-outline ui-press inline-flex items-center gap-1.5 px-4 py-2 text-sm"
          @click="printHandover"
        >
          <AppIcon name="print" class="h-3.5 w-3.5" aria-hidden="true" />
          {{ t("shiftClose.printHandover") }}
        </button>
        <RouterLink
          :to="{ name: 'owner-home' }"
          class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-2 text-sm"
        >
          <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
          {{ t("shiftClose.done") }}
        </RouterLink>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { RouterLink } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import { useTenantStore } from "../stores/tenant";
import api from "../lib/api";

defineOptions({ name: "OwnerShiftClose" });

const { t } = useI18n();
const toast = useToastStore();
const tenant = useTenantStore();

const report = ref(null);
const drawer = ref(null);
const drawerTransactions = ref([]);
const loading = ref(false);
const error = ref("");
const closing = ref(false);
const countedInput = ref("");

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

const fmtTime = (iso) => {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
};

// Determine which drawer state to show
const openDrawer = computed(() => drawer.value?.status === "open" ? drawer.value : null);
const closedDrawer = computed(() => drawer.value?.status === "closed" ? drawer.value : null);

const overShortValue = computed(() => {
  if (!closedDrawer.value) return null;
  return Number(closedDrawer.value.over_short) || 0;
});

const overShortLabel = computed(() => {
  if (overShortValue.value === null) return "—";
  const n = overShortValue.value;
  const formatted = fmtMoney(Math.abs(n));
  if (n > 0) return `+${formatted}`;
  if (n < 0) return `-${formatted}`;
  return formatted;
});

const overShortClass = computed(() => {
  const n = overShortValue.value;
  if (n === null) return "border-slate-700 bg-slate-900/40";
  if (n > 0) return "border-emerald-500/40 bg-emerald-500/8 text-emerald-300";
  if (n < 0) return "border-red-500/40 bg-red-500/8 text-red-300";
  return "border-sky-500/30 bg-sky-500/8 text-sky-300";
});

const loadData = async () => {
  loading.value = true;
  error.value = "";
  try {
    // Load drawer current state
    const [drawerResp, reportResp] = await Promise.all([
      api.get("/owner/drawer/current/").catch(() => null),
      api.get("/owner/z-report/").catch(() => null),
    ]);

    if (drawerResp?.data?.session) {
      drawer.value = drawerResp.data.session;
      drawerTransactions.value = drawerResp.data.transactions ?? [];
    } else {
      // No open session — try to get most recent closed session from history
      const histResp = await api.get("/owner/drawer/history/").catch(() => null);
      if (histResp?.data?.sessions?.length) {
        drawer.value = histResp.data.sessions[0];
        drawerTransactions.value = histResp.data.sessions[0].transactions ?? [];
      }
    }

    if (reportResp?.data) {
      report.value = reportResp.data;
    }
  } catch {
    error.value = t("shiftClose.loadError");
  } finally {
    loading.value = false;
  }
};

const closeDrawerNow = async () => {
  const counted = parseFloat(countedInput.value);
  if (isNaN(counted) || counted < 0) return;
  closing.value = true;
  try {
    const { data } = await api.post("/owner/drawer/close/", { counted_total: counted.toFixed(2) });
    drawer.value = data;
    drawerTransactions.value = drawer.value?.transactions ?? drawerTransactions.value;
    toast.show(t("cashDrawer.closeSuccess"), "success");
    // Refresh Z-report after close
    const r = await api.get("/owner/z-report/").catch(() => null);
    if (r?.data) report.value = r.data;
  } catch (err) {
    toast.show(err?.response?.data?.detail || t("cashDrawer.closeError"), "error");
  } finally {
    closing.value = false;
  }
};

const printHandover = () => window.print();

onMounted(loadData);
</script>

<style></style>
