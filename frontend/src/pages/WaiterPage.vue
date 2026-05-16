<template>
  <div class="space-y-4">
    <!-- Status tabs -->
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
    </div>

    <!-- Loading skeleton -->
    <div v-if="waiter.loading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="i"
        class="h-28 animate-pulse rounded-2xl border border-slate-700/40 bg-slate-800/40"
      />
    </div>

    <!-- Error -->
    <div v-else-if="waiter.error" class="rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-5 text-center">
      <p class="text-sm text-red-300">{{ waiter.error }}</p>
      <button class="mt-3 text-xs text-slate-400 underline hover:text-slate-300" @click="reload">
        {{ t('waiterPage.retry') }}
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="visibleOrders.length === 0"
      class="rounded-2xl border border-slate-700/30 bg-slate-800/20 px-6 py-12 text-center"
    >
      <p class="text-2xl">✓</p>
      <p class="mt-2 text-sm font-medium text-slate-300">{{ t('waiterPage.noActiveOrders') }}</p>
      <p class="mt-1 text-xs text-slate-500">{{ t('waiterPage.noActiveOrdersBody') }}</p>
    </div>

    <!-- Order cards -->
    <div v-else class="space-y-3">
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
            <span v-else>{{ actionLabel(order.status) }}</span>
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

const { t } = useI18n();
const waiter = useWaiterStore();

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

const actionLabel = (s) => ({
  pending: t("waiterPage.actionAccept"),
  confirmed: t("waiterPage.actionPreparing"),
  preparing: t("waiterPage.actionReady"),
  ready: t("waiterPage.actionDone"),
}[s] ?? "");

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
