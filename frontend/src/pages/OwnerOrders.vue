<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="ui-panel space-y-3 p-4 sm:p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="space-y-1">
          <p class="ui-section-kicker">{{ t("ownerOrders.kicker") }}</p>
          <h1 class="text-2xl font-semibold text-white">{{ t("ownerOrders.title") }}</h1>
          <p class="text-sm text-slate-400">{{ t("ownerOrders.description") }}</p>
        </div>
        <button class="ui-btn-outline px-3 py-1.5 text-sm" :disabled="order.ordersLoading" @click="refresh">
          <AppIcon name="refresh" class="h-3.5 w-3.5" />
          {{ t("ownerOrders.refreshOrders") }}
        </button>
      </div>

      <!-- Status filter tabs -->
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          type="button"
          class="rounded-full border px-3 py-1 text-xs font-semibold transition-colors"
          :class="activeStatus === tab.value
            ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
            : 'border-slate-700 text-slate-300 hover:border-slate-600'"
          @click="setFilter(tab.value)"
        >
          {{ tab.label }}
          <span v-if="tab.count > 0" class="ml-1 rounded-full bg-slate-700 px-1.5 py-0.5 text-[10px]">{{ tab.count }}</span>
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="order.ordersLoading" class="ui-panel p-8 text-center text-slate-400 text-sm">
      {{ t("common.loading") }}
    </div>

    <!-- Error -->
    <div v-else-if="order.ordersError" class="ui-panel border-red-500/30 p-5 text-sm text-red-300">
      {{ order.ordersError }}
    </div>

    <!-- Empty -->
    <div v-else-if="!filteredOrders.length" class="ui-panel p-8 text-center text-slate-400 text-sm">
      {{ t("ownerOrders.noOrders") }}
    </div>

    <!-- Order list -->
    <div v-else class="space-y-3">
      <article
        v-for="o in filteredOrders"
        :key="o.id"
        class="ui-panel space-y-4 p-4 sm:p-5"
        :class="o.status === 'pending' ? 'border-amber-500/40' : o.status === 'cancelled' ? 'border-red-500/20' : ''"
      >
        <!-- Order header -->
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1.5">
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-mono text-base font-bold text-white">{{ o.order_number }}</span>
              <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold" :class="statusClass(o.status)">
                {{ statusLabel(o.status) }}
              </span>
              <span class="ui-data-strip">{{ fulfillmentLabel(o) }}</span>
            </div>
            <p class="text-xs text-slate-400">{{ formatTime(o.created_at) }}</p>
          </div>
          <div class="text-right">
            <p class="text-lg font-bold text-[var(--color-secondary)]">{{ formatCurrency(o.total, o.currency) }}</p>
            <p class="text-xs text-slate-400">{{ t("ownerOrders.itemsCount", { count: o.items_count }, o.items_count) }}</p>
          </div>
        </div>

        <!-- Customer info -->
        <div v-if="o.customer_name || o.customer_phone" class="grid gap-2 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs sm:grid-cols-2">
          <div v-if="o.customer_name">
            <span class="text-slate-500">{{ t("ownerOrders.customer") }}</span>
            <span class="ml-1.5 font-medium text-slate-100">{{ o.customer_name }}</span>
          </div>
          <div v-if="o.customer_phone">
            <a :href="`tel:${o.customer_phone}`" class="font-medium text-sky-300 hover:text-sky-200">{{ o.customer_phone }}</a>
          </div>
          <div v-if="o.delivery_address" class="sm:col-span-2">
            <span class="text-slate-500">{{ t("ownerOrders.delivery") }}</span>
            <span class="ml-1.5 text-slate-200">{{ o.delivery_address }}</span>
          </div>
        </div>

        <!-- Items -->
        <div class="space-y-1.5">
          <div
            v-for="item in o.items"
            :key="item.dish_slug + item.note"
            class="flex items-start justify-between gap-2 rounded-xl border border-slate-800 bg-slate-950/30 px-3 py-2 text-xs"
          >
            <div class="space-y-0.5">
              <p class="font-semibold text-slate-100">{{ item.qty }}× {{ item.dish_name }}</p>
              <p v-if="item.options?.length" class="text-slate-400">
                {{ t("ownerOrders.options") }}: {{ item.options.map(o => o.name).join(", ") }}
              </p>
              <p v-if="item.note" class="text-slate-400">{{ item.note }}</p>
            </div>
            <p class="shrink-0 font-medium text-slate-200">{{ formatCurrency(item.subtotal, o.currency) }}</p>
          </div>
          <p v-if="o.customer_note" class="rounded-xl border border-slate-800 bg-slate-950/30 px-3 py-2 text-xs text-slate-300">
            <span class="font-semibold text-slate-400">{{ t("ownerOrders.note") }}:</span> {{ o.customer_note }}
          </p>
        </div>

        <!-- Owner note + estimate -->
        <div v-if="editingId === o.id" class="space-y-2 rounded-xl border border-slate-700 bg-slate-900/60 p-3">
          <label class="block space-y-1 text-xs text-slate-400">
            {{ t("ownerOrders.ownerNote") }}
            <input v-model="editNote" maxlength="300" class="ui-input mt-1 text-sm" />
          </label>
          <label class="block space-y-1 text-xs text-slate-400">
            {{ t("ownerOrders.setEstimate") }}
            <input v-model.number="editMinutes" type="number" min="0" max="180" class="ui-input mt-1 w-32 text-sm" :placeholder="t('ownerOrders.minutesPlaceholder')" />
          </label>
          <div class="flex gap-2">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="saveNote(o)">
              {{ t("ownerOrders.saveNote") }}
            </button>
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="editingId = null">{{ t("common.close") }}</button>
          </div>
        </div>

        <div v-else class="flex flex-wrap items-center gap-2">
          <span v-if="o.owner_note" class="text-xs text-slate-400">
            <span class="font-semibold">{{ t("ownerOrders.ownerNote") }}:</span> {{ o.owner_note }}
          </span>
          <span v-if="o.estimated_ready_minutes" class="ui-data-strip text-emerald-200">
            {{ t("ownerOrders.estimatedReady", { minutes: o.estimated_ready_minutes }) }}
          </span>
        </div>

        <!-- Action buttons -->
        <div class="flex flex-wrap items-center gap-2">
          <template v-if="o.status === 'pending'">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'confirmed')">
              {{ t("ownerOrders.confirm") }}
            </button>
            <button class="ui-btn-outline border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:border-red-400" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'cancelled')">
              {{ t("ownerOrders.cancel") }}
            </button>
          </template>
          <template v-else-if="o.status === 'confirmed'">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'preparing')">
              {{ t("ownerOrders.startPreparing") }}
            </button>
            <button class="ui-btn-outline border-red-500/40 px-3 py-1.5 text-xs text-red-300 hover:border-red-400" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'cancelled')">
              {{ t("ownerOrders.cancel") }}
            </button>
          </template>
          <template v-else-if="o.status === 'preparing'">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'ready')">
              {{ t("ownerOrders.markReady") }}
            </button>
          </template>
          <template v-else-if="o.status === 'ready'">
            <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="order.updatingOrderId === o.id" @click="updateStatus(o, 'completed')">
              {{ t("ownerOrders.complete") }}
            </button>
          </template>

          <button
            v-if="['pending','confirmed','preparing','ready'].includes(o.status)"
            class="ui-btn-outline px-3 py-1.5 text-xs"
            @click="openEdit(o)"
          >
            {{ t("ownerOrders.ownerNote") }}
          </button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useOrderStore } from "../stores/order";
import { useToastStore } from "../stores/toast";

const { t } = useI18n();
const order = useOrderStore();
const toast = useToastStore();

const activeStatus = ref("");
const editingId = ref(null);
const editNote = ref("");
const editMinutes = ref(null);

const statusTabs = computed(() => {
  const counts = {};
  order.orders.forEach((o) => { counts[o.status] = (counts[o.status] || 0) + 1; });
  return [
    { value: "", label: t("ownerOrders.allStatuses"), count: 0 },
    { value: "pending", label: t("ownerOrders.statusPending"), count: counts.pending || 0 },
    { value: "confirmed", label: t("ownerOrders.statusConfirmed"), count: counts.confirmed || 0 },
    { value: "preparing", label: t("ownerOrders.statusPreparing"), count: counts.preparing || 0 },
    { value: "ready", label: t("ownerOrders.statusReady"), count: counts.ready || 0 },
    { value: "completed", label: t("ownerOrders.statusCompleted"), count: counts.completed || 0 },
    { value: "cancelled", label: t("ownerOrders.statusCancelled"), count: counts.cancelled || 0 },
  ];
});

const filteredOrders = computed(() => {
  if (!activeStatus.value) return order.orders;
  return order.orders.filter((o) => o.status === activeStatus.value);
});

const setFilter = (val) => {
  activeStatus.value = val;
};

const refresh = () => order.fetchOrders();

const statusClass = (s) => ({
  pending: "bg-amber-500/20 text-amber-200 border border-amber-500/30",
  confirmed: "bg-sky-500/20 text-sky-200 border border-sky-500/30",
  preparing: "bg-violet-500/20 text-violet-200 border border-violet-500/30",
  ready: "bg-emerald-500/20 text-emerald-200 border border-emerald-500/30",
  completed: "bg-slate-700 text-slate-300",
  cancelled: "bg-red-500/20 text-red-300 border border-red-500/30",
}[s] || "bg-slate-700 text-slate-300");

const statusLabel = (s) => ({
  pending: t("ownerOrders.statusPending"),
  confirmed: t("ownerOrders.statusConfirmed"),
  preparing: t("ownerOrders.statusPreparing"),
  ready: t("ownerOrders.statusReady"),
  completed: t("ownerOrders.statusCompleted"),
  cancelled: t("ownerOrders.statusCancelled"),
}[s] || s);

const fulfillmentLabel = (o) => {
  if (o.fulfillment_type === "table") return t("ownerOrders.fulfillmentTable", { table: o.table_label || "?" });
  if (o.fulfillment_type === "delivery") return t("ownerOrders.fulfillmentDelivery");
  if (o.fulfillment_type === "pickup") return t("ownerOrders.fulfillmentPickup");
  return "";
};

const formatCurrency = (amount, currency = "USD") => {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(amount) || 0);
  } catch {
    return `${currency} ${Number(amount).toFixed(2)}`;
  }
};

const formatTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return t("ownerOrders.justNow");
  if (diffMin < 60) return `${diffMin}m`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ${diffMin % 60}m`;
  return d.toLocaleDateString();
};

const updateStatus = async (o, newStatus) => {
  try {
    await order.updateOrderStatus(o.id, { status: newStatus });
    toast.show(t("ownerOrders.updated"), "success");
  } catch {
    toast.show(t("ownerOrders.updateFailed"), "error");
  }
};

const openEdit = (o) => {
  editingId.value = o.id;
  editNote.value = o.owner_note || "";
  editMinutes.value = o.estimated_ready_minutes ?? null;
};

const saveNote = async (o) => {
  try {
    await order.updateOrderStatus(o.id, {
      owner_note: editNote.value,
      estimated_ready_minutes: editMinutes.value ?? null,
    });
    editingId.value = null;
    toast.show(t("ownerOrders.updated"), "success");
  } catch {
    toast.show(t("ownerOrders.updateFailed"), "error");
  }
};

// ── New-order alert ──────────────────────────────────────────────────────────
const knownOrderIds = ref(new Set());

const playAlertSound = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    // Two quick ascending beeps
    [0, 0.18].forEach((delay, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = "sine";
      osc.frequency.setValueAtTime(i === 0 ? 780 : 980, ctx.currentTime + delay);
      gain.gain.setValueAtTime(0.35, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.25);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.25);
    });
  } catch {
    // AudioContext not available (e.g. SSR or blocked)
  }
};

const showBrowserNotification = (count) => {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  new Notification(t("ownerOrders.newOrderNotifTitle", { count }), {
    body: t("ownerOrders.newOrderNotifBody"),
    icon: "/favicon.ico",
    tag: "new-order",
    renotify: true,
  });
};

const checkForNewOrders = (freshOrders) => {
  if (!knownOrderIds.value.size) {
    // First load — seed known IDs without alerting
    freshOrders.forEach((o) => knownOrderIds.value.add(o.id));
    return;
  }
  const newPending = freshOrders.filter(
    (o) => o.status === "pending" && !knownOrderIds.value.has(o.id)
  );
  freshOrders.forEach((o) => knownOrderIds.value.add(o.id));
  if (newPending.length) {
    playAlertSound();
    showBrowserNotification(newPending.length);
    toast.show(t("ownerOrders.newOrderNotifTitle", { count: newPending.length }), "info");
  }
};

const requestNotificationPermission = async () => {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "default") {
    await Notification.requestPermission();
  }
};

// ─────────────────────────────────────────────────────────────────────────────

let pollTimer = null;
onMounted(async () => {
  await requestNotificationPermission();
  const initial = await order.fetchOrders();
  if (Array.isArray(initial)) checkForNewOrders(initial);
  else checkForNewOrders(order.orders);

  pollTimer = setInterval(async () => {
    await order.fetchOrders(activeStatus.value);
    checkForNewOrders(order.orders);
  }, 30000);
});
onUnmounted(() => clearInterval(pollTimer));
</script>
