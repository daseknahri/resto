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
        <div class="flex flex-wrap items-center gap-2">
          <button
            class="ui-btn-outline px-3 py-1.5 text-sm"
            :class="soundEnabled ? '' : 'opacity-50'"
            :title="soundEnabled ? t('ownerOrders.muteAlerts') : t('ownerOrders.unmuteAlerts')"
            @click="soundEnabled = !soundEnabled"
          >
            {{ soundEnabled ? "🔔" : "🔕" }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-sm" :disabled="!order.orders.length" @click="exportCsv">
            ⬇ {{ t("ownerOrders.exportCsv") }}
          </button>
          <button class="ui-btn-outline px-3 py-1.5 text-sm" :disabled="order.ordersLoading" @click="refresh">
            <AppIcon name="refresh" class="h-3.5 w-3.5" />
            {{ t("ownerOrders.refreshOrders") }}
          </button>
        </div>
      </div>

      <!-- Today's stats bar -->
      <div class="grid grid-cols-3 gap-2 rounded-xl border border-slate-800 bg-slate-950/50 px-3 py-3">
        <div class="text-center">
          <p class="text-xl font-bold text-white tabular-nums">{{ todayStats.count }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerOrders.todayOrders") }}</p>
        </div>
        <div class="border-x border-slate-800 text-center">
          <p class="text-xl font-bold text-[var(--color-secondary)] tabular-nums">{{ formatCurrency(todayStats.revenue, todayStats.currency) }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerOrders.todayRevenue") }}</p>
        </div>
        <div class="text-center">
          <p
            class="text-xl font-bold tabular-nums transition-colors"
            :class="todayStats.pending > 0 ? 'text-amber-400' : 'text-white'"
          >{{ todayStats.pending }}</p>
          <p class="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{{ t("ownerOrders.todayPending") }}</p>
        </div>
      </div>

      <!-- Search + date filter row -->
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model.trim="searchQuery"
          class="ui-input min-w-0 flex-1 text-sm"
          :placeholder="t('ownerOrders.searchPlaceholder')"
          @input="searchQuery = $event.target.value"
        />
        <div class="flex flex-wrap gap-1">
          <button
            v-for="d in dateTabs"
            :key="d.value"
            type="button"
            class="rounded-full border px-3 py-1 text-xs font-semibold transition-colors"
            :class="activeDateFilter === d.value
              ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]'
              : 'border-slate-700 text-slate-300 hover:border-slate-600'"
            @click="activeDateFilter = d.value"
          >
            {{ d.label }}
          </button>
        </div>
        <button
          v-if="searchQuery || activeDateFilter !== 'all'"
          class="rounded-full border border-slate-700 px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
          @click="searchQuery = ''; activeDateFilter = 'all'"
        >✕</button>
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

      <!-- Active filter summary -->
      <p v-if="filteredOrders.length !== order.orders.length" class="text-xs text-slate-500">
        {{ t("ownerOrders.showingFiltered", { shown: filteredOrders.length, total: order.orders.length }) }}
      </p>
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
        class="ui-panel space-y-4 p-4 sm:p-5 transition-colors"
        :class="orderCardClass(o)"
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
              <!-- Age warning badge -->
              <span
                v-if="orderAgeMin(o) >= 5 && ['pending', 'confirmed'].includes(o.status)"
                class="rounded-full px-2 py-0.5 text-[10px] font-bold"
                :class="orderAgeMin(o) >= 10
                  ? 'bg-red-500/25 text-red-300'
                  : 'bg-amber-500/25 text-amber-300'"
              >
                ⏱ {{ orderAgeMin(o) }}m
              </span>
            </div>
            <p class="text-xs text-slate-400">{{ formatTime(o.created_at) }}</p>
          </div>
          <div class="text-right">
            <p class="text-lg font-bold text-[var(--color-secondary)]">{{ formatCurrency(o.total, o.currency) }}</p>
            <p class="text-xs text-slate-400">{{ itemCountLabel(o.items_count) }}</p>
          </div>
        </div>

        <!-- Customer info -->
        <div v-if="o.customer_name || o.customer_phone" class="grid gap-2 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-2 text-xs sm:grid-cols-2">
          <div v-if="o.customer_name">
            <span class="text-slate-500">{{ t("ownerOrders.customer") }}</span>
            <span class="ml-1.5 font-medium text-slate-100">{{ o.customer_name }}</span>
          </div>
          <div v-if="o.customer_phone" class="flex flex-wrap items-center gap-2">
            <a :href="`tel:${o.customer_phone}`" class="font-medium text-sky-300 hover:text-sky-200">{{ o.customer_phone }}</a>
            <a
              :href="orderWhatsappUrl(o.customer_phone)"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 hover:border-emerald-400/60 hover:bg-emerald-500/20"
            >
              💬 {{ t("ownerOrders.whatsapp") }}
            </a>
          </div>
          <div v-if="o.delivery_address" class="sm:col-span-2">
            <span class="text-slate-500">{{ t("ownerOrders.delivery") }}</span>
            <span class="ml-1.5 text-slate-200">{{ o.delivery_address }}</span>
            <a
              v-if="orderMapUrl(o)"
              :href="orderMapUrl(o)"
              target="_blank"
              rel="noopener noreferrer"
              class="ml-2 inline-flex items-center gap-1 rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold text-sky-300 hover:border-sky-400/60 hover:bg-sky-500/20"
            >
              📍 {{ t("ownerOrders.openMap") }}
            </a>
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

          <!-- Print ticket -->
          <button
            class="ui-btn-outline px-3 py-1.5 text-xs"
            @click="printTicket(o)"
          >
            🖨 {{ t("ownerOrders.printTicket") }}
          </button>
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useOrderStore } from "../stores/order";
import { useToastStore } from "../stores/toast";

const { t, itemCountLabel } = useI18n();
const order = useOrderStore();
const toast = useToastStore();

const activeStatus = ref("");
const activeDateFilter = ref("all");
const searchQuery = ref("");
const editingId = ref(null);
const editNote = ref("");
const editMinutes = ref(null);

// Sound preference — persisted in localStorage per hostname
const SOUND_KEY = typeof window === "undefined" ? "orders:sound" : `orders:sound:${window.location.hostname}`;
const soundEnabled = ref((() => {
  try { return localStorage.getItem(SOUND_KEY) !== "off"; } catch { return true; }
})());
watch(soundEnabled, (val) => {
  try { localStorage.setItem(SOUND_KEY, val ? "on" : "off"); } catch { /* ignore */ }
});

// ── Date filter tabs ──────────────────────────────────────────────────────────
const dateTabs = computed(() => [
  { value: "all",       label: t("ownerOrders.dateAll") },
  { value: "today",     label: t("ownerOrders.dateToday") },
  { value: "yesterday", label: t("ownerOrders.dateYesterday") },
  { value: "week",      label: t("ownerOrders.dateLast7") },
]);

// ── Status tabs ───────────────────────────────────────────────────────────────
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

// ── Today's stats ─────────────────────────────────────────────────────────────
const todayStats = computed(() => {
  const today = new Date().toDateString();
  const todayOrders = order.orders.filter((o) => new Date(o.created_at).toDateString() === today);
  const pending = todayOrders.filter((o) => o.status === "pending").length;
  const revenue = todayOrders.reduce((sum, o) => sum + (Number(o.total) || 0), 0);
  const currency = todayOrders.find((o) => o.currency)?.currency || "USD";
  return { count: todayOrders.length, revenue, pending, currency };
});

// ── Filtered + sorted orders ──────────────────────────────────────────────────
const STATUS_SORT = { pending: 0, confirmed: 1, preparing: 2, ready: 3, completed: 4, cancelled: 5 };

const filteredOrders = computed(() => {
  const now = new Date();
  const todayStr = now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const yesterdayStr = yesterday.toDateString();
  const weekAgo = new Date(now);
  weekAgo.setDate(now.getDate() - 6);
  weekAgo.setHours(0, 0, 0, 0);

  const q = searchQuery.value.toLowerCase();

  let base = order.orders.filter((o) => {
    // Status filter
    if (activeStatus.value && o.status !== activeStatus.value) return false;

    // Date filter
    if (activeDateFilter.value !== "all") {
      const d = new Date(o.created_at);
      if (activeDateFilter.value === "today" && d.toDateString() !== todayStr) return false;
      if (activeDateFilter.value === "yesterday" && d.toDateString() !== yesterdayStr) return false;
      if (activeDateFilter.value === "week" && d < weekAgo) return false;
    }

    // Search filter
    if (q) {
      const haystack = [
        o.order_number,
        o.customer_name,
        o.customer_phone,
        o.delivery_address,
        o.table_label,
      ].filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(q)) return false;
    }

    return true;
  });

  return [...base].sort((a, b) => {
    const sd = (STATUS_SORT[a.status] ?? 9) - (STATUS_SORT[b.status] ?? 9);
    if (sd !== 0) return sd;
    // Within same status: newest first
    return new Date(b.created_at) - new Date(a.created_at);
  });
});

const setFilter = (val) => { activeStatus.value = val; };
const refresh = () => order.fetchOrders();

// ── Helpers ───────────────────────────────────────────────────────────────────
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
  const diffMin = Math.floor((now - d) / 60000);
  if (diffMin < 1) return t("ownerOrders.justNow");
  if (diffMin < 60) return `${diffMin}m`;
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ${diffMin % 60}m`;
  return d.toLocaleDateString();
};

// ── Delivery helpers ──────────────────────────────────────────────────────────
const orderMapUrl = (o) => {
  if (o.delivery_location_url) return o.delivery_location_url;
  const lat = o.delivery_lat;
  const lng = o.delivery_lng;
  if (lat != null && lng != null) return `https://maps.google.com/?q=${lat},${lng}`;
  return null;
};

const orderWhatsappUrl = (phone) => {
  if (!phone) return "#";
  const digits = String(phone).replace(/\D/g, "");
  return `https://wa.me/${digits}`;
};

// ── Order age ─────────────────────────────────────────────────────────────────
const orderAgeMin = (o) => Math.floor((Date.now() - new Date(o.created_at)) / 60000);

const orderCardClass = (o) => {
  if (["pending", "confirmed"].includes(o.status)) {
    const age = orderAgeMin(o);
    if (age >= 10) return "border-red-500/60 bg-red-950/5";
    if (age >= 5)  return "border-amber-400/60";
    return "border-amber-500/40";
  }
  if (o.status === "cancelled") return "border-red-500/20";
  return "";
};

// ── Status actions ────────────────────────────────────────────────────────────
const updateStatus = async (o, newStatus) => {
  try {
    await order.updateOrderStatus(o.id, { status: newStatus });
    toast.show(t("ownerOrders.updated"), "success");
    // After confirming, immediately open the note/ETA panel so the owner can
    // set an estimated ready time in the same action without a second click.
    if (newStatus === "confirmed") {
      const fresh = order.orders.find((x) => x.id === o.id) || o;
      openEdit(fresh);
    }
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

// ── Print ticket ──────────────────────────────────────────────────────────────
const printTicket = (o) => {
  const itemRows = (o.items || []).map((item) => {
    const opts = item.options?.length ? `<div style="font-size:11px;color:#555">${item.options.map((x) => x.name).join(", ")}</div>` : "";
    const note = item.note ? `<div style="font-size:11px;color:#555;font-style:italic">${item.note}</div>` : "";
    return `<tr>
      <td style="padding:3px 0;vertical-align:top">
        <strong>${item.qty}×</strong> ${item.dish_name}${opts}${note}
      </td>
      <td style="padding:3px 0;text-align:right;white-space:nowrap;vertical-align:top">
        ${formatCurrency(item.subtotal, o.currency)}
      </td>
    </tr>`;
  }).join("");

  const meta = [
    fulfillmentLabel(o),
    o.customer_name ? `Customer: ${o.customer_name}` : "",
    o.customer_phone ? `Phone: ${o.customer_phone}` : "",
    o.delivery_address ? `Address: ${o.delivery_address}` : "",
    new Date(o.created_at).toLocaleString(),
  ].filter(Boolean).map((line) => `<div>${line}</div>`).join("");

  const note = o.customer_note
    ? `<div style="border-top:1px dashed #000;margin-top:8px;padding-top:6px"><strong>Note:</strong> ${o.customer_note}</div>`
    : "";

  const html = `<!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <title>Order ${o.order_number}</title>
    <style>
      * { margin:0; padding:0; box-sizing:border-box; }
      body { font-family: 'Courier New', monospace; font-size: 13px; width: 300px; padding: 12px; }
      h1 { font-size: 18px; text-align: center; letter-spacing: 1px; border-bottom: 2px dashed #000; padding-bottom: 8px; margin-bottom: 8px; }
      .meta { font-size: 11px; margin-bottom: 8px; line-height: 1.6; }
      table { width: 100%; border-collapse: collapse; }
      .divider { border-top: 1px dashed #000; margin: 8px 0; }
      .total td { font-weight: bold; font-size: 15px; padding: 4px 0; }
      .footer { text-align: center; font-size: 10px; color: #666; margin-top: 12px; border-top: 1px dashed #000; padding-top: 8px; }
      @media print { @page { margin: 0; size: 80mm auto; } }
    </style>
  </head><body>
    <h1>#${o.order_number}</h1>
    <div class="meta">${meta}</div>
    <div class="divider"></div>
    <table>${itemRows}</table>
    <div class="divider"></div>
    <table><tr class="total"><td>TOTAL</td><td style="text-align:right">${formatCurrency(o.total, o.currency)}</td></tr></table>
    ${note}
    <div class="footer">Printed ${new Date().toLocaleTimeString()}</div>
  </body></html>`;

  const win = window.open("", "_blank", "width=420,height=620");
  if (!win) { toast.show(t("ownerOrders.printBlocked"), "error"); return; }
  win.document.write(html);
  win.document.close();
  win.focus();
  setTimeout(() => { win.print(); win.close(); }, 300);
};

// ── CSV export ────────────────────────────────────────────────────────────────
const exportCsv = () => {
  const cols = [
    "order_number", "status", "fulfillment_type", "table_label",
    "customer_name", "customer_phone", "delivery_address",
    "total", "currency", "items_count", "customer_note", "owner_note",
    "estimated_ready_minutes", "created_at",
  ];
  const header = cols.join(",");
  const rows = filteredOrders.value.map((o) =>
    cols.map((col) => {
      const val = o[col] ?? "";
      return `"${String(val).replace(/"/g, '""')}"`;
    }).join(",")
  );
  const csv = [header, ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `orders-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

// ── New-order alert ───────────────────────────────────────────────────────────
const knownOrderIds = ref(new Set());
const lastAlertTime = ref(0);
const RECURRING_ALERT_MS = 2 * 60 * 1000; // re-ping every 2 min while pending orders sit

const playAlertSound = () => {
  if (!soundEnabled.value) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
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
    // AudioContext not available
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
    // First load — seed known IDs, no alert
    freshOrders.forEach((o) => knownOrderIds.value.add(o.id));
    return;
  }
  const newPending = freshOrders.filter(
    (o) => o.status === "pending" && !knownOrderIds.value.has(o.id),
  );
  freshOrders.forEach((o) => knownOrderIds.value.add(o.id));
  if (newPending.length) {
    playAlertSound();
    showBrowserNotification(newPending.length);
    toast.show(t("ownerOrders.newOrderNotifTitle", { count: newPending.length }), "info");
    lastAlertTime.value = Date.now();
  }
};

const requestNotificationPermission = async () => {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "default") await Notification.requestPermission();
};

// ── Polling (visibility-aware) ────────────────────────────────────────────────
let pollTimer = null;

const doPoll = async () => {
  // Always fetch all orders (no status filter) — filtering is client-side only.
  // Passing activeStatus to the API would replace the full list with a subset,
  // making other status groups disappear until the next manual refresh.
  const fresh = await order.fetchOrders("", { silent: true });
  const orders = Array.isArray(fresh) ? fresh : order.orders;
  checkForNewOrders(orders);

  // Recurring alert: re-ping if there are still unhandled pending orders
  const hasPending = orders.some((o) => o.status === "pending");
  const cooldownPassed = Date.now() - lastAlertTime.value > RECURRING_ALERT_MS;
  if (hasPending && knownOrderIds.value.size > 0 && cooldownPassed) {
    playAlertSound();
    lastAlertTime.value = Date.now();
  }
};

const onPageVisible = () => {
  // Immediately refresh when the owner switches back to this tab
  if (typeof document !== "undefined" && document.visibilityState === "visible") {
    doPoll();
  }
};

onMounted(async () => {
  await requestNotificationPermission();
  const initial = await order.fetchOrders();
  checkForNewOrders(Array.isArray(initial) ? initial : order.orders);

  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onPageVisible);
  }

  pollTimer = setInterval(() => {
    // Skip the API call when the tab is in the background — runs on resume instead
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    doPoll();
  }, 15000); // 15 s — faster than layout's 30 s
});

onUnmounted(() => {
  clearInterval(pollTimer);
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", onPageVisible);
  }
});
</script>
