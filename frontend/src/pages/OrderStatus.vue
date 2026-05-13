<template>
  <div class="space-y-4 px-3 py-4 pb-24 sm:px-4">
    <!-- Loading -->
    <div v-if="loading && !orderData" class="ui-panel p-10 text-center text-slate-400 text-sm">
      {{ t("common.loading") }}
    </div>

    <!-- Not found -->
    <div v-else-if="notFound" class="ui-panel p-8 text-center space-y-3">
      <p class="text-base font-semibold text-slate-100">{{ t("orderStatus.notFound") }}</p>
      <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline inline-flex px-4 py-2 text-sm">
        {{ t("orderStatus.backToMenu") }}
      </RouterLink>
    </div>

    <template v-else-if="orderData">
      <!-- Order-ready banner -->
      <div
        v-if="orderData.status === 'ready'"
        class="ui-reveal rounded-2xl border border-emerald-400/60 bg-emerald-500/15 p-4 text-center shadow-lg shadow-emerald-900/20 sm:p-5"
      >
        <p class="text-2xl font-bold text-emerald-200">🎉 {{ t("orderStatus.orderReadyTitle") }}</p>
        <p class="mt-1 text-sm text-emerald-100/80">
          {{ fulfillmentLabel(orderData) === t("orderStatus.fulfillmentDelivery") ? t("orderStatus.readyBodyDelivery") : t("orderStatus.readyBodyPickup") }}
        </p>
      </div>

      <!-- Header -->
      <div class="ui-hero-ribbon ui-reveal p-4 sm:p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("orderStatus.kicker") }}</p>
            <h1 class="ui-display text-2xl font-semibold text-white">
              {{ t("orderStatus.orderNumber", { number: orderData.order_number }) }}
            </h1>
            <div class="flex flex-wrap items-center gap-2 mt-1">
              <span class="rounded-full px-3 py-1 text-xs font-semibold" :class="statusClass(orderData.status)">
                {{ statusLabel(orderData.status) }}
              </span>
              <span v-if="orderData.fulfillment_type" class="ui-chip">{{ fulfillmentLabel(orderData) }}</span>
            </div>
          </div>
          <div class="text-right space-y-1">
            <p class="text-2xl font-bold text-[var(--color-secondary)]">{{ formatCurrency(orderData.total, orderData.currency) }}</p>
            <p class="text-xs text-slate-400">{{ t("orderStatus.items") }}: {{ orderData.items_count }}</p>
          </div>
        </div>
      </div>

      <!-- Status timeline -->
      <div class="ui-panel p-4 sm:p-5">
        <div class="flex items-center justify-between gap-1">
          <div
            v-for="(step, idx) in statusSteps"
            :key="step.value"
            class="flex flex-1 flex-col items-center gap-1.5"
          >
            <div
              class="flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-bold transition-colors"
              :class="stepClass(step.value)"
            >
              <span v-if="isStepDone(step.value)">✓</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <p class="text-center text-[10px] leading-tight text-slate-400 sm:text-xs">{{ step.label }}</p>
            <div
              v-if="idx < statusSteps.length - 1"
              class="absolute hidden"
            />
          </div>
        </div>
        <!-- Progress bar -->
        <div class="mt-3 h-1.5 w-full rounded-full bg-slate-800">
          <div
            class="h-full rounded-full bg-[var(--color-secondary)] transition-all duration-500"
            :style="{ width: `${progressPercent}%` }"
          />
        </div>
      </div>

      <!-- Restaurant message -->
      <div
        v-if="orderData.owner_note || orderData.estimated_ready_minutes"
        class="ui-panel border-emerald-500/30 bg-emerald-500/5 p-4 space-y-2"
      >
        <p v-if="orderData.estimated_ready_minutes" class="text-sm font-semibold text-emerald-200">
          ⏱ {{ t("orderStatus.estimatedReady", { minutes: orderData.estimated_ready_minutes }) }}
        </p>
        <p v-if="orderData.owner_note" class="text-sm text-slate-200">
          <span class="text-slate-400 text-xs block mb-0.5">{{ t("orderStatus.ownerNote") }}</span>
          {{ orderData.owner_note }}
        </p>
      </div>

      <!-- Items -->
      <div class="ui-panel p-4 sm:p-5 space-y-3">
        <h2 class="text-sm font-semibold text-slate-300">{{ t("orderStatus.items") }}</h2>
        <div
          v-for="item in orderData.items"
          :key="item.dish_name + item.note"
          class="flex items-start justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/30 px-3 py-2.5 text-sm"
        >
          <div class="space-y-0.5">
            <p class="font-semibold text-slate-100">{{ item.qty }}× {{ item.dish_name }}</p>
            <p v-if="item.options?.length" class="text-xs text-slate-400">
              {{ item.options.map(o => o.name).join(", ") }}
            </p>
            <p v-if="item.note" class="text-xs text-slate-400">{{ item.note }}</p>
          </div>
          <p class="shrink-0 font-medium text-[var(--color-secondary)]">{{ formatCurrency(item.subtotal, orderData.currency) }}</p>
        </div>

        <div class="flex justify-between border-t border-slate-800 pt-3">
          <span class="text-sm font-semibold text-slate-300">{{ t("orderStatus.total") }}</span>
          <span class="text-base font-bold text-white">{{ formatCurrency(orderData.total, orderData.currency) }}</span>
        </div>
      </div>

      <!-- Auto-refresh notice + back -->
      <div class="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
        <span v-if="isLiveStatus">{{ t("orderStatus.autoRefresh", { seconds: POLL_INTERVAL_S }) }}</span>
        <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline inline-flex px-3 py-1.5 text-xs">
          {{ t("orderStatus.backToMenu") }}
        </RouterLink>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";

const props = defineProps({
  orderNumber: { type: String, required: true },
});

const { t } = useI18n();

const POLL_INTERVAL_S = 15;
const orderData = ref(null);
const loading = ref(false);
const notFound = ref(false);
const readyAlertShown = ref(false);

const isLiveStatus = computed(() =>
  orderData.value && !["completed", "cancelled"].includes(orderData.value.status)
);

const statusSteps = computed(() => [
  { value: "pending", label: t("orderStatus.statusPending") },
  { value: "confirmed", label: t("orderStatus.statusConfirmed") },
  { value: "preparing", label: t("orderStatus.statusPreparing") },
  { value: "ready", label: t("orderStatus.statusReady") },
  { value: "completed", label: t("orderStatus.statusCompleted") },
]);

const STATUS_ORDER = ["pending", "confirmed", "preparing", "ready", "completed"];

const currentStepIndex = computed(() => {
  const s = orderData.value?.status;
  if (s === "cancelled") return -1;
  return STATUS_ORDER.indexOf(s);
});

const progressPercent = computed(() => {
  if (currentStepIndex.value < 0) return 0;
  return Math.round(((currentStepIndex.value + 1) / STATUS_ORDER.length) * 100);
});

const isStepDone = (stepValue) => {
  const stepIdx = STATUS_ORDER.indexOf(stepValue);
  return stepIdx <= currentStepIndex.value;
};

const stepClass = (stepValue) => {
  const stepIdx = STATUS_ORDER.indexOf(stepValue);
  const curr = currentStepIndex.value;
  if (stepIdx < curr) return "border-[var(--color-secondary)] bg-[var(--color-secondary)] text-black";
  if (stepIdx === curr) return "border-[var(--color-secondary)] bg-[var(--color-secondary)]/20 text-[var(--color-secondary)]";
  return "border-slate-700 bg-slate-900 text-slate-600";
};

const statusClass = (s) => ({
  pending: "bg-amber-500/20 text-amber-200 border border-amber-500/30",
  confirmed: "bg-sky-500/20 text-sky-200 border border-sky-500/30",
  preparing: "bg-violet-500/20 text-violet-200 border border-violet-500/30",
  ready: "bg-emerald-500/20 text-emerald-200 border border-emerald-500/30",
  completed: "bg-slate-700 text-slate-300",
  cancelled: "bg-red-500/20 text-red-300 border border-red-500/30",
}[s] || "bg-slate-700 text-slate-300");

const statusLabel = (s) => ({
  pending: t("orderStatus.statusPending"),
  confirmed: t("orderStatus.statusConfirmed"),
  preparing: t("orderStatus.statusPreparing"),
  ready: t("orderStatus.statusReady"),
  completed: t("orderStatus.statusCompleted"),
  cancelled: t("orderStatus.statusCancelled"),
}[s] || s);

const fulfillmentLabel = (o) => {
  if (o.fulfillment_type === "table") return t("orderStatus.fulfillmentTable", { table: o.table_label || "?" });
  if (o.fulfillment_type === "delivery") return t("orderStatus.fulfillmentDelivery");
  if (o.fulfillment_type === "pickup") return t("orderStatus.fulfillmentPickup");
  return "";
};

const formatCurrency = (amount, currency = "USD") => {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(amount) || 0);
  } catch {
    return `${currency} ${Number(amount).toFixed(2)}`;
  }
};

// ── Order-ready alert ──────────────────────────────────────────────────────────

const playReadyChime = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const notes = [523.25, 659.25, 783.99]; // C5, E5, G5
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = "sine";
      osc.frequency.value = freq;
      const start = ctx.currentTime + i * 0.18;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.28, start + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, start + 0.52);
      osc.start(start);
      osc.stop(start + 0.55);
    });
  } catch {
    // AudioContext blocked or unavailable — silent fallback
  }
};

const sendReadyBrowserNotification = () => {
  try {
    if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
    const n = new Notification(t("orderStatus.readyNotifTitle"), {
      body: t("orderStatus.readyNotifBody", { number: props.orderNumber }),
      tag: `order-ready-${props.orderNumber}`,
      renotify: false,
    });
    // Auto-close after 8 seconds
    setTimeout(() => n.close(), 8000);
  } catch {
    // Notification API unavailable
  }
};

const triggerReadyAlert = () => {
  if (readyAlertShown.value) return;
  readyAlertShown.value = true;
  playReadyChime();
  sendReadyBrowserNotification();
};

// Watch for status transitioning to "ready" during polling
watch(
  () => orderData.value?.status,
  (newStatus, oldStatus) => {
    if (newStatus === "ready" && oldStatus && oldStatus !== "ready") {
      triggerReadyAlert();
    }
  }
);

const fetchStatus = async () => {
  loading.value = true;
  try {
    const res = await api.get(`/order-status/${props.orderNumber}/`);
    const prev = orderData.value?.status;
    orderData.value = res.data;
    // If the order was already "ready" when the page first loaded, show alert too
    if (res.data?.status === "ready" && !prev) {
      triggerReadyAlert();
    }
    notFound.value = false;
  } catch (err) {
    if (err?.response?.status === 404) {
      notFound.value = true;
    }
  } finally {
    loading.value = false;
  }
};

let pollTimer = null;
onMounted(() => {
  // Request notification permission proactively (non-blocking)
  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }
  fetchStatus();
  pollTimer = setInterval(() => {
    if (isLiveStatus.value) fetchStatus();
  }, POLL_INTERVAL_S * 1000);
});
onUnmounted(() => clearInterval(pollTimer));
</script>
