<template>
  <div
    class="kitchen-shell"
    :class="{ 'kitchen-fullscreen': isFullscreen }"
  >
    <!-- Top bar -->
    <div class="kitchen-topbar" role="banner">
      <div class="flex items-center gap-2.5">
        <span class="ui-kicker">{{ t("kitchen.title") }}</span>
        <!-- Offline / syncing indicator -->
        <span
          v-if="!waiter.isOnline"
          class="rounded-full border border-red-500/40 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold text-red-400"
          role="status"
          aria-live="polite"
        >{{ t("kitchen.offline") }}</span>
        <span
          v-else-if="waiter.isSyncing || waiter.queueLength > 0"
          class="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400"
          role="status"
          aria-live="polite"
        >{{ t("kitchen.syncing") }}</span>
      </div>

      <div class="flex items-center gap-3">
        <!-- Active order count -->
        <span class="text-sm font-bold text-white tabular-nums" aria-live="polite" aria-atomic="true">
          {{ t("kitchen.activeCount", { n: activeOrders.length }) }}
        </span>
        <!-- Clock -->
        <span class="font-mono text-sm tabular-nums text-slate-400" aria-hidden="true">{{ clockDisplay }}</span>
        <!-- Fullscreen toggle -->
        <button
          class="kitchen-fs-btn ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
          :aria-label="isFullscreen ? t('kitchen.exitFullscreen') : t('kitchen.enterFullscreen')"
          :aria-pressed="isFullscreen"
          @click="toggleFullscreen"
        >
          <svg v-if="isFullscreen" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4" aria-hidden="true">
            <path fill-rule="evenodd" d="M5 10a.75.75 0 01.75-.75h8.5a.75.75 0 010 1.5h-8.5A.75.75 0 015 10z" clip-rule="evenodd"/>
            <path d="M3 3.75A.75.75 0 013.75 3h3.5a.75.75 0 010 1.5h-2v2a.75.75 0 01-1.5 0v-2.75zm10 0a.75.75 0 01.75-.75h3.5a.75.75 0 01.75.75v2.75a.75.75 0 01-1.5 0v-2h-2a.75.75 0 01-.75-.75zM3 16.25A.75.75 0 013.75 17h3.5a.75.75 0 000-1.5h-2v-2a.75.75 0 00-1.5 0v2.75zm10.75.75a.75.75 0 01-.75-.75v-2.75a.75.75 0 011.5 0v2h2a.75.75 0 010 1.5h-2.75z"/>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="h-4 w-4" aria-hidden="true">
            <path d="M13.28 7.78l3.22-3.22v2.69a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.69l-3.22 3.22a.75.75 0 001.06 1.06zM2 17.25v-4.5a.75.75 0 011.5 0v2.69l3.22-3.22a.75.75 0 011.06 1.06L4.56 16.5h2.69a.75.75 0 010 1.5h-4.5a.75.75 0 01-.75-.75zM12.22 13.28l3.22 3.22h-2.69a.75.75 0 000 1.5h4.5a.75.75 0 00.75-.75v-4.5a.75.75 0 00-1.5 0v2.69l-3.22-3.22a.75.75 0 10-1.06 1.06zM3.5 4.56l3.22 3.22a.75.75 0 001.06-1.06L4.56 3.5h2.69a.75.75 0 000-1.5h-4.5a.75.75 0 00-.75.75v4.5a.75.75 0 001.5 0V4.56z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Station filter bar -->
    <nav class="kitchen-filter-bar" :aria-label="t('kitchen.filterAll')">
      <button
        v-for="f in stationFilters"
        :key="f.value"
        class="kitchen-filter-btn ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
        :class="stationFilter === f.value ? 'kitchen-filter-btn--active' : ''"
        :aria-pressed="stationFilter === f.value"
        @click="stationFilter = f.value"
      >
        {{ f.label }}
        <span v-if="f.count > 0" class="kitchen-filter-count" aria-hidden="true">{{ f.count }}</span>
      </button>
    </nav>

    <!-- Loading: skeleton cards matching the kitchen-grid layout -->
    <div v-if="waiter.loading" class="kitchen-grid">
      <div v-for="i in 3" :key="i" class="kitchen-card animate-pulse border-slate-700/40 bg-slate-800/20">
        <div class="h-1 w-full bg-slate-700/60" />
        <div class="flex items-start justify-between gap-2 px-4 pt-4">
          <div class="flex-1 space-y-2">
            <div class="h-5 w-24 rounded bg-slate-700/60" />
            <div class="h-3 w-36 rounded bg-slate-800/60" />
          </div>
          <div class="flex flex-col items-end gap-2 shrink-0">
            <div class="h-5 w-12 rounded-full bg-slate-700/60" />
            <div class="h-4 w-16 rounded-full bg-slate-800/50" />
          </div>
        </div>
        <div class="mt-4 flex-1 space-y-2 px-4">
          <div v-for="j in 3" :key="j" class="flex items-center gap-2">
            <div class="h-4 w-6 rounded bg-slate-700/50" />
            <div class="h-3 rounded bg-slate-800/50" :style="`width: ${60 + j * 15}px`" />
          </div>
        </div>
        <div class="m-4 mt-auto h-9 rounded-xl bg-slate-700/40" />
      </div>
    </div>

    <!-- All-clear -->
    <div v-else-if="!activeOrders.length" class="kitchen-empty" role="status" aria-live="polite">
      <!-- Checkmark icon -->
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-16 w-16 text-emerald-400/70" aria-hidden="true">
        <path d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/>
      </svg>
      <p class="mt-3 text-xl font-semibold text-slate-200">{{ t("kitchen.allClear") }}</p>
      <p class="mt-1 text-sm text-slate-500">{{ t("kitchen.allClearBody") }}</p>
    </div>

    <!-- Order grid -->
    <div v-else class="kitchen-grid" role="list" :aria-label="t('kitchen.activeCount', { n: activeOrders.length })">
      <article
        v-for="(order, index) in activeOrders"
        :key="order.id"
        class="kitchen-card ui-reveal"
        :class="cardClass(order.status)"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        role="listitem"
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
              #{{ order.order_number }} · {{ timeAgo(order.created_at) }}<span v-if="order.customer_name"> · {{ order.customer_name }}</span>
            </p>
          </div>
          <div class="flex shrink-0 flex-col items-end gap-1.5">
            <!-- Elapsed timer badge -->
            <span
              class="rounded-full border px-2 py-0.5 text-[11px] font-bold tabular-nums"
              :class="elapsedBadgeClass(elapsedMinutes(order))"
              :aria-label="`${elapsedMinutes(order)}${t('kitchen.elapsedMin')} ${t('kitchen.elapsed')}`"
            >{{ elapsedMinutes(order) }}{{ t('kitchen.elapsedMin') }}</span>
            <!-- Status chip -->
            <span
              class="rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
              :class="chipClass(order.status)"
            >{{ t(`kitchen.status_${order.status}`) }}</span>
          </div>
        </div>

        <!-- Items -->
        <ul class="mt-3 flex-1 space-y-1 overflow-y-auto px-4" :aria-label="t('kitchen.tapItemReady')">
          <li
            v-for="(item, idx) in order.items"
            :key="item.id ?? idx"
            class="kitchen-item select-none"
            :class="[item.id != null ? 'cursor-pointer ui-press' : '', item.is_ready ? 'opacity-45 line-through' : '']"
            :title="item.id != null ? t('kitchen.tapItemReady') : ''"
            :aria-pressed="item.id != null ? item.is_ready : undefined"
            :role="item.id != null ? 'button' : undefined"
            @click="toggleItem(order, item)"
          >
            <span class="kitchen-qty" :class="headlineColorClass(order.status)" aria-hidden="true">{{ item.qty }}×</span>
            <span class="kitchen-name">{{ item.dish_name }}</span>
            <span v-if="item.note" class="ms-1 shrink-0 text-[11px] italic text-slate-500">({{ item.note }})</span>
            <span v-if="item.is_ready" class="ms-auto shrink-0 text-emerald-400" aria-hidden="true">
              <!-- Checkmark icon -->
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-4 w-4" aria-hidden="true">
                <path fill-rule="evenodd" d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd"/>
              </svg>
            </span>
          </li>
        </ul>

        <!-- Notes -->
        <div v-if="order.customer_note || order.owner_note" class="mt-2 space-y-1 border-t border-slate-700/40 px-4 pt-2 text-xs">
          <p v-if="order.customer_note" class="text-slate-400">
            <span class="font-semibold text-slate-300">{{ t("kitchen.noteCustomer") }}: </span>{{ order.customer_note }}
          </p>
          <p v-if="order.owner_note" class="text-amber-300/80">
            <span class="font-semibold">{{ t("kitchen.noteStaff") }}: </span>{{ order.owner_note }}
          </p>
        </div>

        <!-- Action button -->
        <div class="mt-auto space-y-2 px-4 pb-4 pt-3">
          <button
            v-if="waiter.nextStatus(order)"
            class="kitchen-action-btn ui-touch-target"
            :class="[actionBtnClass(order.status), waiter.updatingOrderIds.has(order.id) ? 'opacity-50 pointer-events-none' : '']"
            :disabled="waiter.updatingOrderIds.has(order.id)"
            :aria-busy="waiter.updatingOrderIds.has(order.id)"
            @click="advance(order.id)"
          >
            <span v-if="waiter.updatingOrderIds.has(order.id)" class="animate-pulse" aria-hidden="true">…</span>
            <span v-else>{{ actionLabel(order) }}</span>
          </button>
          <p v-else class="text-center text-xs italic text-slate-500">{{ t("kitchen.handedOff") }}</p>
          <button
            class="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-600/70 py-1.5 text-xs font-medium text-slate-300 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 hover:border-slate-400 hover:text-white ui-press"
            @click="printTicket(order)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="h-3.5 w-3.5 shrink-0" aria-hidden="true">
              <path fill-rule="evenodd" d="M4 2a1.5 1.5 0 0 0-1.5 1.5v2.879a2.25 2.25 0 0 0-.659 1.591v3.158A2.25 2.25 0 0 0 4.09 13.5H4.5v.5A1.5 1.5 0 0 0 6 15.5h4a1.5 1.5 0 0 0 1.5-1.5v-.5h.41a2.25 2.25 0 0 0 2.249-2.372l-.21-3.158A2.25 2.25 0 0 0 13.5 6.379V3.5A1.5 1.5 0 0 0 12 2H4Zm8.5 4.379-.097-.172A.75.75 0 0 0 11.75 6h-7.5a.75.75 0 0 0-.653.207L3.5 6.379V3.5a.5.5 0 0 1 .5-.5h8a.5.5 0 0 1 .5.5v2.879ZM10 8.5a.5.5 0 0 1 .5.5v4.5a.5.5 0 0 1-.5.5H6a.5.5 0 0 1-.5-.5V9a.5.5 0 0 1 .5-.5h4Z" clip-rule="evenodd"/>
            </svg>
            {{ t("ownerOrders.printTicket") }}
          </button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "../composables/useI18n";
import { useWaiterStore } from "../stores/waiter";
import { usePrintTicket } from "../composables/usePrintTicket";

// Explicit name so <KeepAlive :exclude> in OwnerLayout reliably skips this page
// (live kitchen display — polls and must mount & unmount normally).
defineOptions({ name: "OwnerKitchen" });

const { t, currentLocale } = useI18n();
const waiter = useWaiterStore();
const { printTicket } = usePrintTicket();

const isFullscreen = ref(false);
const stationFilter = ref("all");

// Reactive "now" for elapsed timers — updated every tick with the clock
const nowMs = ref(Date.now());

// Active orders — exclude completed/cancelled, apply station filter
const ACTIVE_STATUSES = new Set(["pending", "confirmed", "preparing", "ready"]);

const allActiveOrders = computed(() =>
  waiter.orders.filter((o) => ACTIVE_STATUSES.has(o.status))
);

const activeOrders = computed(() => {
  if (stationFilter.value === "all") return allActiveOrders.value;
  return allActiveOrders.value.filter((o) => o.fulfillment_type === stationFilter.value);
});

// Station filter options with live counts
const stationFilters = computed(() => {
  const all = allActiveOrders.value;
  const count = (type) => all.filter((o) => o.fulfillment_type === type).length;
  return [
    { value: "all",      label: t("kitchen.filterAll"),      count: all.length },
    { value: "table",    label: t("kitchen.filterTables"),   count: count("table") },
    { value: "pickup",   label: t("kitchen.pickup"),         count: count("pickup") },
    { value: "delivery", label: t("kitchen.delivery"),       count: count("delivery") },
  ];
});

// Elapsed time helpers
const elapsedMinutes = (order) =>
  Math.floor((nowMs.value - new Date(order.created_at).getTime()) / 60_000);

const elapsedBadgeClass = (minutes) => {
  if (minutes >= 20) return "border-red-500/50 bg-red-500/15 text-red-300";
  if (minutes >= 10) return "border-amber-500/50 bg-amber-500/15 text-amber-300";
  return "border-slate-600/60 bg-slate-700/40 text-slate-400";
};

// ── Clock ─────────────────────────────────────────────────────────────────────
const clockDisplay = ref("");
let clockTimer = null;
const updateClock = () => {
  const now = new Date();
  nowMs.value = now.getTime();
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

const onKitchenPageVisible = () => {
  if (document.visibilityState === "visible") doPoll();
};

onMounted(async () => {
  waiter.setupConnectivityListeners();
  updateClock();
  clockTimer = setInterval(updateClock, 10_000);
  document.addEventListener("fullscreenchange", onFullscreenChange);
  document.addEventListener("visibilitychange", onKitchenPageVisible);

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
  document.removeEventListener("visibilitychange", onKitchenPageVisible);
  waiter.teardownConnectivityListeners();
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
});

const advance = (orderId) => waiter.advanceStatus(orderId);
const toggleItem = (order, item) => {
  if (item?.id == null) return; // older payloads without item ids → no-op
  waiter.toggleItemReady(order.id, item.id, !item.is_ready);
};

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
  preparing: t("kitchen.actionReady"),
  ready: order.fulfillment_type === "delivery" ? t("kitchen.actionOutForDelivery") : t("kitchen.actionDone"),
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

/* Station filter bar */
.kitchen-filter-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.kitchen-filter-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border-radius: 9999px;
  border: 1px solid rgba(51, 65, 85, 0.6);
  background: rgba(30, 41, 59, 0.5);
  padding: 0.3rem 0.85rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: rgb(148, 163, 184);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.kitchen-filter-btn:hover {
  border-color: rgba(100, 116, 139, 0.8);
  color: rgb(203, 213, 225);
}

.kitchen-filter-btn--active {
  border-color: rgba(245, 158, 11, 0.5);
  background: rgba(245, 158, 11, 0.12);
  color: rgb(251, 191, 36);
}

.kitchen-fs-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.75rem;
  border: 1px solid rgba(51, 65, 85, 0.6);
  background: rgba(30, 41, 59, 0.55);
  padding: 0.4rem 0.5rem;
  color: rgb(148, 163, 184);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.kitchen-fs-btn:hover {
  border-color: rgba(100, 116, 139, 0.8);
  color: rgb(203, 213, 225);
  background: rgba(30, 41, 59, 0.8);
}

.kitchen-filter-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.2rem;
  height: 1.2rem;
  border-radius: 9999px;
  background: rgba(51, 65, 85, 0.8);
  font-size: 0.65rem;
  font-weight: 700;
  color: rgb(148, 163, 184);
  padding: 0 0.25rem;
}

.kitchen-filter-btn--active .kitchen-filter-count {
  background: rgba(245, 158, 11, 0.25);
  color: rgb(251, 191, 36);
}
</style>
