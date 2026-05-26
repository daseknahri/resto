<template>
  <div
    class="kitchen-shell"
    :class="{ 'kitchen-fullscreen': isFullscreen }"
  >
    <!-- Top bar -->
    <div class="kitchen-topbar">
      <div class="flex items-center gap-3">
        <span class="text-xs font-semibold uppercase tracking-widest text-slate-400">
          {{ t("kitchen.title") }}
        </span>
        <!-- Offline / syncing indicator -->
        <span
          v-if="!waiter.isOnline"
          class="rounded-full border border-red-500/40 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-400"
        >{{ t("kitchen.offline") }}</span>
        <span
          v-else-if="waiter.isSyncing || waiter.queueLength > 0"
          class="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400"
        >{{ t("kitchen.syncing") }}</span>
      </div>

      <div class="flex items-center gap-3">
        <!-- Active order count -->
        <span class="text-sm font-bold text-white tabular-nums">
          {{ t("kitchen.activeCount", { n: activeOrders.length }) }}
        </span>
        <!-- Clock -->
        <span class="font-mono text-sm tabular-nums text-slate-400">{{ clockDisplay }}</span>
        <!-- Fullscreen toggle -->
        <button
          class="rounded-xl border border-slate-700 bg-slate-800/60 px-2.5 py-1.5 text-xs text-slate-400 hover:border-slate-600 hover:text-slate-200 transition-colors"
          :title="isFullscreen ? t('kitchen.exitFullscreen') : t('kitchen.enterFullscreen')"
          @click="toggleFullscreen"
        >{{ isFullscreen ? "⤓" : "⤢" }}</button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="waiter.loading" class="kitchen-empty">
      <p class="text-2xl text-slate-500">{{ t("common.loading") }}</p>
    </div>

    <!-- All-clear -->
    <div v-else-if="!activeOrders.length" class="kitchen-empty">
      <p class="text-5xl">✓</p>
      <p class="mt-3 text-xl font-semibold text-slate-300">{{ t("kitchen.allClear") }}</p>
      <p class="mt-1 text-sm text-slate-500">{{ t("kitchen.allClearBody") }}</p>
    </div>

    <!-- Order grid -->
    <div v-else class="kitchen-grid">
      <div
        v-for="order in activeOrders"
        :key="order.id"
        class="kitchen-card"
        :class="cardClass(order.status)"
      >
        <!-- Status strip at top -->
        <div class="kitchen-strip" :class="stripClass(order.status)" />

        <!-- Order headline -->
        <div class="flex items-start justify-between gap-2 px-4 pt-4">
          <div class="min-w-0 flex-1">
            <p class="kitchen-headline truncate" :class="headlineColorClass(order.status)">
              {{ orderHeadline(order) }}
            </p>
            <p class="mt-0.5 text-xs text-slate-500 tabular-nums">
              #{{ order.order_number }} · {{ timeAgo(order.created_at) }}
            </p>
          </div>
          <span
            class="shrink-0 rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
            :class="chipClass(order.status)"
          >{{ t(`kitchen.status_${order.status}`) }}</span>
        </div>

        <!-- Items -->
        <ul class="mt-3 flex-1 space-y-1 overflow-y-auto px-4">
          <li
            v-for="(item, idx) in order.items"
            :key="idx"
            class="kitchen-item"
          >
            <span class="kitchen-qty" :class="headlineColorClass(order.status)">{{ item.qty }}×</span>
            <span class="kitchen-name">{{ item.dish_name }}</span>
            <span v-if="item.note" class="ml-1 shrink-0 text-[11px] italic text-slate-500">({{ item.note }})</span>
          </li>
        </ul>

        <!-- Notes -->
        <div v-if="order.customer_note || order.owner_note" class="mt-2 space-y-1 px-4 text-xs">
          <p v-if="order.customer_note" class="text-slate-400">
            <span class="font-semibold text-slate-300">{{ t("kitchen.noteCustomer") }}: </span>{{ order.customer_note }}
          </p>
          <p v-if="order.owner_note" class="text-amber-300/80">
            <span class="font-semibold">{{ t("kitchen.noteStaff") }}: </span>{{ order.owner_note }}
          </p>
        </div>

        <!-- Action button -->
        <div class="mt-auto px-4 pb-4 pt-3">
          <button
            v-if="waiter.nextStatus(order.status)"
            class="kitchen-action-btn"
            :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '']"
            :disabled="waiter.updatingOrderIds.has(order.id)"
            @click="advance(order.id)"
          >
            <span v-if="waiter.updatingOrderIds.has(order.id)" class="animate-pulse">…</span>
            <span v-else>{{ actionLabel(order) }}</span>
          </button>
          <p v-else class="text-center text-xs text-slate-500 italic">{{ t("kitchen.handedOff") }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import { useWaiterStore } from "../stores/waiter";

const { t, currentLocale } = useI18n();
const waiter = useWaiterStore();

const isFullscreen = ref(false);

// Active orders — exclude completed/cancelled
const ACTIVE_STATUSES = new Set(["pending", "confirmed", "preparing", "ready"]);
const activeOrders = computed(() =>
  waiter.orders.filter((o) => ACTIVE_STATUSES.has(o.status))
);

// ── Clock ─────────────────────────────────────────────────────────────────────
const clockDisplay = ref("");
let clockTimer = null;
const updateClock = () => {
  const now = new Date();
  clockDisplay.value = new Intl.DateTimeFormat(currentLocale.value, { hour: "2-digit", minute: "2-digit" }).format(now);
};

// ── Fullscreen ────────────────────────────────────────────────────────────────
const toggleFullscreen = () => {
  if (!document.fullscreenEnabled) {
    isFullscreen.value = !isFullscreen.value;
    return;
  }
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {
      isFullscreen.value = !isFullscreen.value;
    });
    isFullscreen.value = true;
  } else {
    document.exitFullscreen();
    isFullscreen.value = false;
  }
};

const onFullscreenChange = () => {
  isFullscreen.value = Boolean(document.fullscreenElement);
};

// ── Polling ───────────────────────────────────────────────────────────────────
let pollTimer = null;
let prevPendingIds = new Set();

const playAlert = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.2].forEach((delay) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 660;
      gain.gain.setValueAtTime(0.4, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.35);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.4);
    });
  } catch { /* AudioContext unavailable */ }
};

const checkNewOrders = (orders) => {
  const pendingIds = new Set(orders.filter((o) => o.status === "pending").map((o) => o.id));
  if ([...pendingIds].some((id) => !prevPendingIds.has(id)) && prevPendingIds.size > 0) playAlert();
  prevPendingIds = pendingIds;
};

const doPoll = async () => {
  const results = await waiter.fetchOrders({ silent: true });
  if (Array.isArray(results)) checkNewOrders(results);
};

onMounted(async () => {
  waiter.setupConnectivityListeners();
  updateClock();
  clockTimer = setInterval(updateClock, 10_000);
  document.addEventListener("fullscreenchange", onFullscreenChange);

  const initial = await waiter.fetchOrders();
  if (Array.isArray(initial)) {
    prevPendingIds = new Set(initial.filter((o) => o.status === "pending").map((o) => o.id));
  }

  pollTimer = setInterval(() => {
    if (document.visibilityState === "hidden") return;
    doPoll();
  }, 10_000); // 10s for kitchen — faster than regular waiter view
});

onUnmounted(() => {
  clearInterval(pollTimer);
  clearInterval(clockTimer);
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  waiter.teardownConnectivityListeners();
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
});

const advance = (orderId) => waiter.advanceStatus(orderId);

// ── Display helpers ────────────────────────────────────────────────────────────
const orderHeadline = (order) => {
  if (order.fulfillment_type === "table" && order.table_label) return order.table_label;
  if (order.fulfillment_type === "pickup") return t("kitchen.pickup");
  if (order.fulfillment_type === "delivery") return t("kitchen.delivery");
  return `#${order.order_number}`;
};

const timeAgo = (iso) => {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return t("kitchen.justNow");
  if (diff < 3600) return t("kitchen.minsAgo", { n: Math.floor(diff / 60) });
  return t("kitchen.hrsAgo", { n: Math.floor(diff / 3600) });
};

const actionLabel = (order) => ({
  pending: t("kitchen.actionAccept"),
  confirmed: t("kitchen.actionPreparing"),
  preparing: order.fulfillment_type === "delivery" ? t("kitchen.actionOutForDelivery") : t("kitchen.actionReady"),
  ready: order.fulfillment_type === "delivery" ? t("kitchen.actionDelivered") : t("kitchen.actionDone"),
}[order.status] ?? "");

// ── Styling ────────────────────────────────────────────────────────────────────
const cardClass = (s) => ({
  pending:   "border-amber-500/30 bg-amber-500/5",
  confirmed: "border-sky-500/30 bg-sky-500/5",
  preparing: "border-orange-500/30 bg-orange-500/5",
  ready:     "border-emerald-500/30 bg-emerald-500/5",
}[s] ?? "border-slate-700/40 bg-slate-800/20");

const stripClass = (s) => ({
  pending:   "bg-amber-500",
  confirmed: "bg-sky-500",
  preparing: "bg-orange-500",
  ready:     "bg-emerald-500",
}[s] ?? "bg-slate-600");

const headlineColorClass = (s) => ({
  pending:   "text-amber-300",
  confirmed: "text-sky-300",
  preparing: "text-orange-300",
  ready:     "text-emerald-300",
}[s] ?? "text-slate-200");

const chipClass = (s) => ({
  pending:   "border-amber-500/40 bg-amber-500/10 text-amber-300",
  confirmed: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  preparing: "border-orange-500/40 bg-orange-500/10 text-orange-300",
  ready:     "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
}[s] ?? "border-slate-600 bg-slate-700/40 text-slate-300");

const actionBtnClass = (s) => ({
  pending:   "bg-amber-500 hover:bg-amber-400 text-white",
  confirmed: "bg-sky-500 hover:bg-sky-400 text-white",
  preparing: "bg-orange-500 hover:bg-orange-400 text-white",
  ready:     "bg-emerald-500 hover:bg-emerald-400 text-white",
}[s] ?? "bg-slate-600 hover:bg-slate-500 text-white");
</script>

<style scoped>
/* Kitchen shell — overrides the owner layout's max-width container */
.kitchen-shell {
  position: relative;
  min-height: calc(100vh - 8rem);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: #0b0f1a;
  border-radius: 1rem;
  padding: 0.75rem;
}

.kitchen-shell.kitchen-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  border-radius: 0;
  padding: 1rem;
  min-height: 100dvh;
}

.kitchen-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(51, 65, 85, 0.5);
  border-radius: 0.75rem;
  padding: 0.5rem 0.75rem;
  flex-shrink: 0;
}

.kitchen-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 16rem;
  gap: 0.25rem;
  text-align: center;
}

/* Responsive grid: 1 col on phones, 2 on tablet, 3+ on wide kitchen displays */
.kitchen-grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: 1fr;
  flex: 1;
  align-content: start;
}

@media (min-width: 640px) {
  .kitchen-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1024px) {
  .kitchen-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (min-width: 1400px) {
  .kitchen-grid { grid-template-columns: repeat(4, 1fr); }
}

.kitchen-card {
  display: flex;
  flex-direction: column;
  border-radius: 1rem;
  border-width: 1px;
  overflow: hidden;
  min-height: 18rem;
  background: rgba(15, 23, 42, 0.6);
}

.kitchen-strip {
  height: 0.25rem;
  width: 100%;
  flex-shrink: 0;
}

/* Very large — readable at arm's length on a tablet mounted in a kitchen */
.kitchen-headline {
  font-size: clamp(1.75rem, 5vw, 2.5rem);
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.01em;
}

.kitchen-item {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 1rem;
  line-height: 1.4;
  color: rgb(226, 232, 240);
}

.kitchen-qty {
  flex-shrink: 0;
  font-size: 1.05rem;
  font-weight: 700;
}

.kitchen-name {
  min-width: 0;
  word-break: break-word;
}

.kitchen-action-btn {
  width: 100%;
  border-radius: 0.75rem;
  padding: 0.75rem;
  font-size: 1rem;
  font-weight: 700;
  text-align: center;
  transition: opacity 0.15s;
}
</style>
