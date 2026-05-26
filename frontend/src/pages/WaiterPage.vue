<template>
  <div class="space-y-4">
    <!-- Status tabs + New Order button -->
    <div class="flex gap-1.5 overflow-x-auto pb-1">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="shrink-0 rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors"
        :class="activeTab === tab.key
          ? 'border-indigo-500/60 bg-indigo-500/15 text-indigo-300'
          : 'border-slate-700/50 bg-slate-800/40 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span
          v-if="tab.count > 0"
          class="ml-1.5 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full px-1 text-[10px] font-semibold"
          :class="tab.key === 'pending' ? 'bg-amber-500 text-white' : 'bg-slate-600 text-slate-200'"
        >{{ tab.count }}</span>
      </button>
      <!-- Shift summary tab -->
      <button
        class="shrink-0 rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors"
        :class="activeTab === 'shift'
          ? 'border-violet-500/60 bg-violet-500/15 text-violet-300'
          : 'border-slate-700/50 bg-slate-800/40 text-slate-400 hover:border-slate-600 hover:text-slate-300'"
        @click="openShiftSummary"
      >
        {{ t('waiterPage.tabShift') }}
      </button>
      <!-- New Order -->
      <button
        class="ml-auto shrink-0 rounded-xl border border-emerald-500/50 bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-300 transition-colors hover:bg-emerald-500/25"
        @click="showNewOrder = true"
      >
        + {{ t('waiterPage.newOrderBtn') }}
      </button>
    </div>

    <!-- New Order modal -->
    <WaiterNewOrder
      v-if="showNewOrder"
      @close="showNewOrder = false"
      @placed="onOrderPlaced"
    />

    <!-- Loading skeleton (orders only) -->
    <div v-if="activeTab !== 'shift' && waiter.loading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="i"
        class="h-28 animate-pulse rounded-2xl border border-slate-700/40 bg-slate-800/40"
      />
    </div>

    <!-- Error (orders only) -->
    <div v-else-if="activeTab !== 'shift' && waiter.error" class="rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-5 text-center">
      <p class="text-sm text-red-300">{{ waiter.error }}</p>
      <button class="mt-3 text-xs text-slate-400 underline hover:text-slate-300" @click="reload">
        {{ t('waiterPage.retry') }}
      </button>
    </div>

    <!-- Empty state (orders only) -->
    <div
      v-else-if="activeTab !== 'shift' && visibleOrders.length === 0"
      class="rounded-2xl border border-slate-700/30 bg-slate-800/20 px-6 py-12 text-center"
    >
      <p class="text-2xl">✓</p>
      <p class="mt-2 text-sm font-medium text-slate-300">{{ t('waiterPage.noActiveOrders') }}</p>
      <p class="mt-1 text-xs text-slate-500">{{ t('waiterPage.noActiveOrdersBody') }}</p>
    </div>

    <!-- Shift summary panel -->
    <div v-else-if="activeTab === 'shift'" class="space-y-4">
      <!-- Shift start picker -->
      <div class="flex flex-wrap items-end gap-3">
        <div class="space-y-1">
          <label class="text-xs text-slate-400">{{ t('waiterPage.shiftSince') }}</label>
          <input
            v-model="shiftSinceInput"
            type="datetime-local"
            class="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-violet-500 focus:outline-none"
          />
        </div>
        <button
          class="rounded-xl border border-violet-500/40 bg-violet-500/15 px-4 py-2 text-sm font-medium text-violet-300 hover:bg-violet-500/25 disabled:opacity-50 transition-colors"
          :disabled="waiter.shiftSummaryLoading"
          @click="loadShiftSummary"
        >
          {{ waiter.shiftSummaryLoading ? t('waiterPage.shiftLoading') : t('waiterPage.shiftRefresh') }}
        </button>
      </div>

      <!-- Error -->
      <div v-if="waiter.shiftSummaryError" class="rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-4 text-center text-sm text-red-300">
        {{ waiter.shiftSummaryError }}
      </div>

      <!-- Stats grid -->
      <div v-else-if="waiter.shiftSummary" class="grid grid-cols-3 gap-3">
        <div class="rounded-2xl border border-slate-700/50 bg-slate-800/40 p-4 text-center space-y-1">
          <p class="text-3xl font-bold text-white">{{ waiter.shiftSummary.orders_handled }}</p>
          <p class="text-[11px] text-slate-400 uppercase tracking-wide">{{ t('waiterPage.shiftOrders') }}</p>
        </div>
        <div class="rounded-2xl border border-slate-700/50 bg-slate-800/40 p-4 text-center space-y-1">
          <p class="text-3xl font-bold text-emerald-300">{{ shiftRevenue }}</p>
          <p class="text-[11px] text-slate-400 uppercase tracking-wide">{{ t('waiterPage.shiftRevenue') }}</p>
        </div>
        <div class="rounded-2xl border border-slate-700/50 bg-slate-800/40 p-4 text-center space-y-1">
          <p class="text-3xl font-bold text-sky-300">
            {{ waiter.shiftSummary.average_prep_time_minutes != null ? waiter.shiftSummary.average_prep_time_minutes : '—' }}
            <span v-if="waiter.shiftSummary.average_prep_time_minutes != null" class="text-base font-normal text-sky-400/70">m</span>
          </p>
          <p class="text-[11px] text-slate-400 uppercase tracking-wide">{{ t('waiterPage.shiftAvgPrep') }}</p>
        </div>
      </div>

      <!-- Period caption -->
      <p v-if="waiter.shiftSummary" class="text-center text-xs text-slate-500">
        {{ t('waiterPage.shiftPeriod', { hours: waiter.shiftSummary.period_hours }) }}
      </p>

      <!-- Empty state while not yet loaded -->
      <div v-else class="rounded-2xl border border-slate-700/30 bg-slate-800/20 px-6 py-12 text-center">
        <p class="text-sm text-slate-400">{{ t('waiterPage.shiftHint') }}</p>
      </div>
    </div>

    <!-- Order cards -->
    <div v-else-if="activeTab !== 'shift'" class="space-y-3">
      <div
        v-for="order in visibleOrders"
        :key="order.id"
        class="overflow-hidden rounded-2xl border transition-colors"
        :class="statusCardClass(order.status)"
      >
        <!-- Card header -->
        <div class="flex items-start justify-between gap-3 px-4 pt-4">
          <div class="min-w-0">
            <!-- Table / fulfillment label (largest text — for quick scanning) -->
            <p class="truncate text-lg font-bold text-white leading-tight">
              {{ orderHeadline(order) }}
            </p>
            <p class="mt-0.5 text-xs text-slate-400">
              #{{ order.order_number }} · {{ timeAgo(order.created_at) }}
            </p>
          </div>
          <!-- Status chip -->
          <span
            class="shrink-0 rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            :class="statusChipClass(order.status)"
          >{{ t(`waiterPage.status_${order.status}`) }}</span>
        </div>

        <!-- Items -->
        <ul class="mt-2 space-y-0.5 px-4">
          <li
            v-for="(item, idx) in order.items"
            :key="idx"
            class="flex items-baseline gap-2 text-sm text-slate-300"
          >
            <span class="shrink-0 font-semibold text-slate-100">{{ item.qty }}×</span>
            <span class="truncate">{{ item.dish_name }}</span>
            <span v-if="item.note" class="shrink-0 text-[10px] italic text-slate-500">({{ item.note }})</span>
          </li>
        </ul>

        <!-- Notes row -->
        <div v-if="order.customer_note || order.owner_note" class="mt-2 space-y-1 px-4">
          <p v-if="order.customer_note" class="text-xs text-slate-400">
            <span class="font-medium text-slate-300">{{ t('waiterPage.customerNote') }}:</span>
            {{ order.customer_note }}
          </p>
          <p v-if="order.owner_note" class="text-xs text-amber-300/80">
            <span class="font-medium">{{ t('waiterPage.staffNote') }}:</span>
            {{ order.owner_note }}
          </p>
        </div>

        <!-- ETA + total -->
        <div class="mt-2 flex items-center gap-4 px-4 text-xs text-slate-500">
          <span v-if="order.estimated_ready_minutes">
            {{ t('waiterPage.eta', { minutes: order.estimated_ready_minutes }) }}
          </span>
          <span>{{ order.total }} {{ order.currency }}</span>
        </div>

        <!-- Action footer -->
        <div class="mt-3 flex items-center gap-2 border-t px-4 py-3" :class="statusBorderClass(order.status)">
          <button
            v-if="waiter.nextStatus(order.status)"
            class="flex-1 rounded-xl py-2.5 text-sm font-semibold transition-opacity"
            :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '']"
            :disabled="waiter.updatingOrderIds.has(order.id)"
            @click="advance(order.id)"
          >
            <span v-if="waiter.updatingOrderIds.has(order.id)">…</span>
            <span v-else>{{ actionLabel(order) }}</span>
          </button>
          <span v-else class="text-xs text-slate-500 italic">{{ t('waiterPage.handedOff') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useI18n } from "../composables/useI18n";
import { useWaiterStore } from "../stores/waiter";
import WaiterNewOrder from "../components/WaiterNewOrder.vue";

const { t, currentLocale } = useI18n();
const waiter = useWaiterStore();

const showNewOrder = ref(false);
const onOrderPlaced = () => {
  // Immediately reload the order list so the new order appears
  waiter.fetchOrders({ silent: true });
};

// ── Shift summary ──────────────────────────────────────────────────────────────
// Default shift start: 8 hours ago, formatted for datetime-local input
const _defaultSince = () => {
  const d = new Date(Date.now() - 8 * 60 * 60 * 1000);
  // Format as YYYY-MM-DDTHH:MM (local time, no seconds/tz for input compatibility)
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const shiftSinceInput = ref(_defaultSince());

const shiftRevenue = computed(() => {
  const s = waiter.shiftSummary;
  if (!s) return "—";
  const num = parseFloat(s.total_revenue || "0");
  if (!s.currency) return num.toFixed(2);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: "currency",
      currency: s.currency,
      maximumFractionDigits: 2,
    }).format(num);
  } catch {
    return `${num.toFixed(2)} ${s.currency}`;
  }
});

const openShiftSummary = () => {
  activeTab.value = "shift";
  if (!waiter.shiftSummary) loadShiftSummary();
};

const loadShiftSummary = () => {
  // Convert local datetime-local value to ISO string
  const raw = shiftSinceInput.value;
  let sinceIso = null;
  if (raw) {
    try {
      sinceIso = new Date(raw).toISOString();
    } catch {
      sinceIso = null;
    }
  }
  waiter.fetchShiftSummary(sinceIso);
};

// ── Tabs ───────────────────────────────────────────────────────────────────────
const activeTab = ref("all");

const tabs = computed(() => [
  { key: "all", label: t("waiterPage.tabAll"), count: waiter.orders.length },
  { key: "pending", label: t("waiterPage.tabPending"), count: waiter.byStatus.pending.length },
  { key: "confirmed", label: t("waiterPage.tabConfirmed"), count: waiter.byStatus.confirmed.length },
  { key: "preparing", label: t("waiterPage.tabPreparing"), count: waiter.byStatus.preparing.length },
  { key: "ready", label: t("waiterPage.tabReady"), count: waiter.byStatus.ready.length },
]);

const visibleOrders = computed(() => {
  if (activeTab.value === "all") return waiter.orders;
  return waiter.byStatus[activeTab.value] ?? [];
});

// ── Polling ────────────────────────────────────────────────────────────────────
let pollTimer = null;
let prevPendingIds = new Set();

const playAlert = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.18].forEach((delay) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.3, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.25);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.25);
    });
  } catch {
    // AudioContext unavailable — silent fail
  }
};

const checkNewOrders = (orders) => {
  const currentPendingIds = new Set(orders.filter((o) => o.status === "pending").map((o) => o.id));
  const isNew = [...currentPendingIds].some((id) => !prevPendingIds.has(id));
  if (isNew && prevPendingIds.size > 0) playAlert();
  prevPendingIds = currentPendingIds;
};

const doPoll = async () => {
  const results = await waiter.fetchOrders({ silent: true });
  if (Array.isArray(results)) checkNewOrders(results);
};

const onVisible = () => {
  if (document.visibilityState === "visible") doPoll();
};

onMounted(async () => {
  const initial = await waiter.fetchOrders();
  if (Array.isArray(initial)) prevPendingIds = new Set(initial.filter((o) => o.status === "pending").map((o) => o.id));
  document.addEventListener("visibilitychange", onVisible);
  pollTimer = setInterval(() => {
    if (document.visibilityState === "hidden") return;
    doPoll();
  }, 15000);
});

onUnmounted(() => {
  clearInterval(pollTimer);
  document.removeEventListener("visibilitychange", onVisible);
});

const reload = () => waiter.fetchOrders();

// ── Actions ────────────────────────────────────────────────────────────────────
const advance = (orderId) => waiter.advanceStatus(orderId);

// ── Display helpers ────────────────────────────────────────────────────────────
const orderHeadline = (order) => {
  if (order.fulfillment_type === "table" && order.table_label) return order.table_label;
  if (order.fulfillment_type === "pickup") return t("waiterPage.pickup");
  if (order.fulfillment_type === "delivery") return t("waiterPage.delivery");
  return order.table_label || `#${order.order_number}`;
};

const timeAgo = (iso) => {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return t("waiterPage.justNow");
  if (diff < 3600) return t("waiterPage.minutesAgo", { n: Math.floor(diff / 60) });
  return t("waiterPage.hoursAgo", { n: Math.floor(diff / 3600) });
};

const actionLabel = (order) => {
  const isDelivery = order.fulfillment_type === "delivery";
  return {
    pending: t("waiterPage.actionAccept"),
    confirmed: t("waiterPage.actionPreparing"),
    preparing: isDelivery ? t("waiterPage.actionOutForDelivery") : t("waiterPage.actionReady"),
    ready: isDelivery ? t("waiterPage.actionDelivered") : t("waiterPage.actionDone"),
  }[order.status] ?? "";
};

// ── Styling ────────────────────────────────────────────────────────────────────
const statusCardClass = (s) => ({
  pending:   "border-amber-500/30 bg-amber-500/5",
  confirmed: "border-sky-500/30 bg-sky-500/5",
  preparing: "border-orange-500/30 bg-orange-500/5",
  ready:     "border-emerald-500/30 bg-emerald-500/5",
}[s] ?? "border-slate-700/40 bg-slate-800/30");

const statusChipClass = (s) => ({
  pending:   "border-amber-500/40 bg-amber-500/10 text-amber-300",
  confirmed: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  preparing: "border-orange-500/40 bg-orange-500/10 text-orange-300",
  ready:     "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
}[s] ?? "border-slate-600 bg-slate-700/40 text-slate-300");

const statusBorderClass = (s) => ({
  pending:   "border-amber-500/20",
  confirmed: "border-sky-500/20",
  preparing: "border-orange-500/20",
  ready:     "border-emerald-500/20",
}[s] ?? "border-slate-700/30");

const actionBtnClass = (s) => ({
  pending:   "bg-amber-500 hover:bg-amber-400 text-white",
  confirmed: "bg-sky-500 hover:bg-sky-400 text-white",
  preparing: "bg-orange-500 hover:bg-orange-400 text-white",
  ready:     "bg-emerald-500 hover:bg-emerald-400 text-white",
}[s] ?? "bg-slate-600 hover:bg-slate-500 text-white");
</script>
