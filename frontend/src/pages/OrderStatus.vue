<template>
  <div class="space-y-4 px-3 py-4 pb-24 sm:px-4">
    <!-- Screen-reader live region: announces status changes as they arrive -->
    <div
      v-if="orderData"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      class="sr-only"
    >{{ statusLabel(orderData?.status) }}</div>

    <!-- Loading skeleton -->
    <div v-if="loading && !orderData" class="space-y-3">
      <div class="animate-pulse rounded-2xl border border-slate-700/60 bg-slate-900/60 p-5 space-y-3">
        <div class="h-2.5 w-16 rounded bg-slate-700/60" />
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-2">
            <div class="h-6 w-40 rounded bg-slate-700/60" />
            <div class="h-5 w-24 rounded-full bg-slate-800/60" />
          </div>
          <div class="h-8 w-20 rounded bg-slate-700/50" />
        </div>
      </div>
      <div class="animate-pulse rounded-2xl border border-slate-700/60 bg-slate-900/60 p-5 space-y-3">
        <div class="h-2.5 w-20 rounded bg-slate-700/60" />
        <div v-for="i in 3" :key="i" class="flex items-center justify-between gap-3">
          <div class="h-3 w-36 rounded bg-slate-800/60" />
          <div class="h-3 w-14 rounded bg-slate-800/50" />
        </div>
      </div>
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
        class="ui-reveal relative overflow-hidden rounded-2xl border border-emerald-400/50 bg-emerald-500/12 p-5 text-center shadow-xl shadow-emerald-900/25 sm:p-6"
      >
        <!-- background glow -->
        <div class="pointer-events-none absolute inset-0 rounded-2xl bg-[radial-gradient(ellipse_at_top,rgba(52,211,153,0.18),transparent_60%)]" />
        <div class="relative space-y-2">
          <p class="text-3xl">🎉</p>
          <p class="text-2xl font-bold text-emerald-200">{{ t("orderStatus.orderReadyTitle") }}</p>
          <p class="text-sm text-emerald-100/75">
            {{ fulfillmentLabel(orderData) === t("orderStatus.fulfillmentDelivery") ? t("orderStatus.readyBodyDelivery") : t("orderStatus.readyBodyPickup") }}
          </p>
        </div>
      </div>

      <!-- Order-cancelled banner -->
      <div
        v-if="orderData.status === 'cancelled'"
        class="ui-reveal rounded-2xl border border-red-400/60 bg-red-500/15 p-4 text-center shadow-lg shadow-red-900/20 sm:p-5"
      >
        <p class="text-2xl font-bold text-red-200">{{ t("orderStatus.cancelledTitle") }}</p>
        <p class="mt-1 text-sm text-red-100/80">{{ t("orderStatus.cancelledBody") }}</p>
        <RouterLink :to="{ name: 'menu' }" class="mt-3 inline-flex rounded-full border border-red-400/50 px-4 py-1.5 text-xs font-semibold text-red-200 hover:bg-red-500/10">
          {{ t("orderStatus.backToMenu") }}
        </RouterLink>
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
            <p class="text-2xl font-bold tabular-nums text-[var(--color-secondary)]">{{ formatCurrency(orderData.total, orderData.currency) }}</p>
            <p class="text-[10px] text-slate-500">{{ t("orderStatus.items") }}: {{ orderData.items_count }}</p>
          </div>
        </div>
      </div>

      <!-- Table order banner -->
      <div
        v-if="orderData.fulfillment_type === 'table'"
        class="ui-reveal rounded-2xl border border-emerald-500/40 bg-emerald-500/12 p-5 text-center"
      >
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400">
          {{ t("orderStatus.tableOrderLabel") }}
        </p>
        <p class="mt-1 text-5xl font-bold text-white tracking-tight">
          {{ orderData.table_label || t("orderStatus.tableUnknown") }}
        </p>
        <p v-if="orderData.customer_name" class="mt-1.5 text-sm font-medium text-slate-300">
          {{ orderData.customer_name }}
        </p>
        <p class="mt-2 text-sm text-emerald-300/75">
          {{ t("orderStatus.tableOrderHint") }}
        </p>
      </div>

      <!-- Delivery address confirmation -->
      <div
        v-if="orderData.fulfillment_type === 'delivery' && orderData.delivery_address"
        class="ui-reveal rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4"
      >
        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
          {{ t("orderStatus.deliveryAddress") }}
        </p>
        <p class="mt-1.5 text-sm text-slate-200">{{ orderData.delivery_address }}</p>
        <a
          v-if="orderData.delivery_location_url &&
                (orderData.delivery_location_url.startsWith('http://') ||
                 orderData.delivery_location_url.startsWith('https://'))"
          :href="orderData.delivery_location_url"
          target="_blank"
          rel="noopener noreferrer"
          class="mt-2 inline-flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300"
        >
          <AppIcon name="location" class="h-3.5 w-3.5" />
          {{ t("orderStatus.openMap") }}
        </a>
      </div>

      <!-- Status timeline -->
      <div class="ui-panel p-4 sm:p-5">
        <div class="flex items-center justify-between gap-1">
          <div
            v-for="(step, idx) in statusSteps"
            :key="step.value"
            class="flex flex-1 flex-col items-center gap-1.5"
          >
            <!-- step circle with optional pulse ring on the active step -->
            <div class="relative flex items-center justify-center">
              <div
                v-if="idx === currentStepIndex && currentStepIndex >= 0 && orderData.status !== 'completed'"
                class="absolute -inset-1.5 animate-ping rounded-full border border-[var(--color-secondary)]/35"
              />
              <div
                class="relative flex h-9 w-9 items-center justify-center rounded-full border-2 text-xs font-bold transition-all duration-500"
                :class="stepClass(step.value)"
              >
                <span v-if="isStepDone(step.value) && idx !== currentStepIndex">✓</span>
                <span v-else-if="idx === currentStepIndex">
                  <!-- spinning dot for current step -->
                  <span class="block h-2.5 w-2.5 rounded-full bg-current" />
                </span>
                <span v-else>{{ idx + 1 }}</span>
              </div>
            </div>
            <p class="text-center text-[10px] leading-tight text-slate-400 sm:text-xs">{{ step.label }}</p>
          </div>
        </div>
        <!-- Progress bar -->
        <div
          class="mt-3 h-1.5 w-full rounded-full bg-slate-800"
          role="progressbar"
          :aria-valuenow="progressPercent"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="statusLabel(orderData?.status)"
        >
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
          <template v-if="countdownSeconds !== null && countdownSeconds > 0">
            ⏱ {{ t("orderStatus.estimatedReady", { minutes: Math.ceil(countdownSeconds / 60) }) }}
            <span class="ml-1 font-mono text-xs font-normal text-emerald-300/70 tabular-nums">
              ({{ Math.floor(countdownSeconds / 60) }}:{{ String(countdownSeconds % 60).padStart(2, "0") }})
            </span>
          </template>
          <template v-else-if="countdownSeconds !== null && countdownSeconds <= 0">
            ⏱ {{ t("orderStatus.readyAnyMoment") }}
          </template>
          <template v-else>
            ⏱ {{ t("orderStatus.estimatedReady", { minutes: orderData.estimated_ready_minutes }) }}
          </template>
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
          class="flex items-start justify-between gap-3 rounded-xl border border-slate-800/70 bg-slate-950/40 px-3 py-2.5 text-sm transition-colors hover:border-slate-700/60"
        >
          <div class="flex items-start gap-2.5 min-w-0">
            <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-800/60 text-[10px] font-bold text-slate-400 tabular-nums">{{ item.qty }}</span>
            <div class="min-w-0 space-y-0.5">
              <p class="font-semibold text-slate-100 truncate">{{ item.dish_name }}</p>
              <p v-if="item.options?.length" class="text-xs text-slate-400">
                {{ item.options.map(o => o.name).join(" · ") }}
              </p>
              <p v-if="item.note" class="text-xs italic text-slate-500">{{ item.note }}</p>
            </div>
          </div>
          <p class="shrink-0 font-semibold text-[var(--color-secondary)] tabular-nums">{{ formatCurrency(item.subtotal, orderData.currency) }}</p>
        </div>

        <!-- Delivery fee breakdown — only shown for delivery orders with a fee -->
        <template v-if="orderData.fulfillment_type === 'delivery' && Number(orderData.delivery_fee) > 0">
          <div class="flex justify-between border-t border-slate-800 pt-3 text-sm text-slate-400">
            <span>{{ t("orderStatus.subtotal") }}</span>
            <span>{{ formatCurrency(Number(orderData.total) - Number(orderData.delivery_fee), orderData.currency) }}</span>
          </div>
          <div class="flex justify-between text-sm text-slate-400">
            <span>{{ t("orderStatus.deliveryFee") }}</span>
            <span>{{ formatCurrency(orderData.delivery_fee, orderData.currency) }}</span>
          </div>
          <div class="flex justify-between border-t border-slate-700 pt-2">
            <span class="text-sm font-semibold text-slate-300">{{ t("orderStatus.total") }}</span>
            <span class="text-base font-bold text-white">{{ formatCurrency(orderData.total, orderData.currency) }}</span>
          </div>
        </template>
        <div v-else class="flex justify-between border-t border-slate-800 pt-3">
          <span class="text-sm font-semibold text-slate-300">{{ t("orderStatus.total") }}</span>
          <span class="text-base font-bold text-white">{{ formatCurrency(orderData.total, orderData.currency) }}</span>
        </div>
        <!-- Wallet credits applied -->
        <div
          v-if="Number(orderData.wallet_amount_paid) > 0"
          class="flex items-center justify-between rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-3 py-2 text-xs"
        >
          <span class="text-emerald-300">{{ t("orderStatus.walletPaid", { amount: formatCurrency(orderData.wallet_amount_paid) }) }}</span>
          <span class="font-semibold text-emerald-200">💰 {{ formatCurrency(orderData.wallet_amount_paid) }}</span>
        </div>
      </div>

      <!-- Receipt message (thank-you note from the restaurant owner) -->
      <div
        v-if="orderData.receipt_message && ['confirmed', 'ready', 'completed'].includes(orderData.status)"
        class="ui-panel ui-reveal p-4 sm:p-5 space-y-1.5 border-[var(--color-secondary)]/25 bg-[var(--color-secondary)]/5"
      >
        <p class="text-xs font-semibold uppercase tracking-[0.15em] text-[var(--color-secondary)]/70">
          {{ t("orderStatus.receiptMessage") }}
        </p>
        <p class="text-sm text-slate-200 leading-relaxed">{{ orderData.receipt_message }}</p>
      </div>

      <!-- Rating prompt (completed, not yet rated) -->
      <div
        v-if="orderData.status === 'completed' && !orderData.has_rating"
        class="ui-panel ui-reveal p-4 sm:p-5 space-y-4"
      >
        <div>
          <p class="text-sm font-semibold text-slate-200">{{ t("orderStatus.rateTitle") }}</p>
          <p class="text-xs text-slate-400 mt-0.5">{{ t("orderStatus.rateSubtitle") }}</p>
        </div>
        <!-- Star picker -->
        <div class="flex gap-2">
          <button
            v-for="star in 5"
            :key="star"
            type="button"
            class="text-3xl leading-none transition-transform hover:scale-110 focus:outline-none"
            :aria-label="t('orderStatus.ratingLabel', { score: star })"
            @click="ratingScore = star"
          >
            <span :class="star <= ratingScore ? 'text-amber-400' : 'text-slate-700'">★</span>
          </button>
        </div>
        <!-- Comment -->
        <textarea
          v-model="ratingComment"
          rows="2"
          :aria-label="t('orderStatus.commentPlaceholder')"
          :placeholder="t('orderStatus.commentPlaceholder')"
          class="ui-textarea w-full resize-none"
        />
        <button
          :disabled="ratingScore === 0 || ratingSubmitting"
          class="ui-btn-primary inline-flex px-5 py-2 text-sm disabled:opacity-40"
          @click="submitRating"
        >
          {{ ratingSubmitting ? t("orderStatus.rateSubmitting") : t("orderStatus.rateSubmit") }}
        </button>
      </div>

      <!-- Already rated — show submitted rating -->
      <div
        v-else-if="orderData.status === 'completed' && orderData.has_rating && orderData.rating"
        class="ui-panel ui-reveal p-4 sm:p-5 space-y-1"
      >
        <p class="text-xs font-semibold uppercase tracking-[0.15em] text-slate-400">{{ t("orderStatus.yourRating") }}</p>
        <div class="flex items-center gap-2">
          <span class="text-2xl text-amber-400">{{ "★".repeat(orderData.rating.score) }}<span class="text-slate-700">{{ "★".repeat(5 - orderData.rating.score) }}</span></span>
          <span class="text-sm font-semibold text-slate-200">{{ orderData.rating.score }}/5</span>
        </div>
        <p v-if="orderData.rating.comment" class="text-sm text-slate-400 italic">{{ orderData.rating.comment }}</p>
      </div>

      <!-- Sign-in nudge for anonymous table orders -->
      <div
        v-if="orderData.fulfillment_type === 'table' && !customerStore.isAuthenticated"
        class="ui-panel ui-reveal p-4 space-y-3"
      >
        <div class="space-y-1">
          <p class="text-sm font-semibold text-slate-100">{{ t("orderStatus.tableSignInNudgeTitle") }}</p>
          <p class="text-xs text-slate-400">{{ t("orderStatus.tableSignInNudgeBody") }}</p>
        </div>
        <button class="ui-btn-primary inline-flex w-full justify-center py-2 text-sm" @click="showAuthModal = true">
          <AppIcon name="user" class="h-3.5 w-3.5" />
          {{ t("orderStatus.tableSignInNudgeButton") }}
        </button>
      </div>

      <!-- Re-order + navigation -->
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span v-if="isLiveStatus" class="text-xs text-slate-500">
          {{ t("orderStatus.autoRefresh", { seconds: POLL_INTERVAL_S }) }}
        </span>
        <div class="flex flex-wrap gap-2">
          <button
            v-if="orderData.items?.some(i => i.dish_slug)"
            class="ui-btn-primary inline-flex px-4 py-2 text-sm"
            @click="reorder"
          >
            {{ t("orderStatus.reorder") }}
          </button>
          <RouterLink :to="{ name: 'menu' }" class="ui-btn-outline inline-flex px-3 py-1.5 text-xs">
            {{ t("orderStatus.backToMenu") }}
          </RouterLink>
        </div>
      </div>
    </template>
  </div>

  <CustomerAuthModal
    v-if="showAuthModal"
    @close="showAuthModal = false"
    @authenticated="showAuthModal = false"
  />
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import CustomerAuthModal from "../components/CustomerAuthModal.vue";
import { useI18n } from "../composables/useI18n";
import { useCurrencyStore } from "../stores/currency";
import { useCartStore } from "../stores/cart";
import { useCustomerStore } from "../stores/customer";
import { useOrderStore } from "../stores/order";
import { useToastStore } from "../stores/toast";
import api from "../lib/api";

const props = defineProps({
  orderNumber: { type: String, required: true },
});

const router = useRouter();
const cart = useCartStore();
const customerStore = useCustomerStore();
const orderStore = useOrderStore();
const toast = useToastStore();
const { t, formatPrice, currentLocale } = useI18n();
const currencyStore = useCurrencyStore();

const showAuthModal = ref(false);

const POLL_INTERVAL_S = 15;
const orderData = ref(null);
const loading = ref(false);
const notFound = ref(false);
const readyAlertShown = ref(false);

// ── Rating ────────────────────────────────────────────────────────────────────
const ratingScore = ref(0);
const ratingComment = ref("");
const ratingSubmitting = ref(false);

const submitRating = async () => {
  if (ratingScore.value === 0 || ratingSubmitting.value) return;
  ratingSubmitting.value = true;
  try {
    await api.post(`/orders/${props.orderNumber}/rate/`, {
      score: ratingScore.value,
      comment: ratingComment.value.trim(),
    });
    toast.show(t("orderStatus.rateSubmitted"), "success");
    // Refresh so has_rating flips to true and the prompt hides
    await fetchStatus();
  } catch {
    toast.show(t("orderStatus.rateError"), "error");
  } finally {
    ratingSubmitting.value = false;
  }
};

const isLiveStatus = computed(() =>
  orderData.value && !["completed", "cancelled"].includes(orderData.value.status)
);

// ── Countdown timer ───────────────────────────────────────────────────────────
const countdownSeconds = ref(null);
let countdownTimer = null;

const updateCountdown = () => {
  const d = orderData.value;
  if (!d?.estimated_ready_minutes || !d?.created_at || !isLiveStatus.value) {
    countdownSeconds.value = null;
    return;
  }
  const readyAt = new Date(d.created_at).getTime() + d.estimated_ready_minutes * 60_000;
  countdownSeconds.value = Math.floor((readyAt - Date.now()) / 1000);
};

const startCountdown = () => {
  clearInterval(countdownTimer);
  updateCountdown();
  countdownTimer = setInterval(updateCountdown, 1000);
};

const stopCountdown = () => {
  clearInterval(countdownTimer);
  countdownTimer = null;
  countdownSeconds.value = null;
};

// ── Re-order ──────────────────────────────────────────────────────────────────
const reorder = () => {
  const items = orderData.value?.items;
  if (!items?.length) return;
  items.forEach((item) => {
    if (!item.dish_slug) return;
    cart.add({
      key: `${item.dish_slug}::`,
      slug: item.dish_slug,
      name: item.dish_name,
      price: Number(item.unit_price || 0),
      currency: item.currency || orderData.value.currency,
      qty: item.qty,
      note: item.note || "",
      option_ids: [],
      option_labels: item.options?.map((o) => o.name).filter(Boolean) || [],
    });
  });
  toast.show(t("orderStatus.reorderAdded"), "success");
  router.push({ name: "cart" });
};

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

const formatCurrency = (amount, currency) => {
  if (!currency) return formatPrice(amount);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount || 0);
  } catch {
    return formatPrice(amount);
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

// Start/stop countdown whenever order data arrives or status changes
watch(
  () => [orderData.value?.estimated_ready_minutes, orderData.value?.created_at, isLiveStatus.value],
  () => {
    if (orderData.value?.estimated_ready_minutes && isLiveStatus.value) startCountdown();
    else stopCountdown();
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

const onStatusPageVisible = () => {
  if (typeof document !== "undefined" && document.visibilityState === "visible" && isLiveStatus.value) {
    fetchStatus();
  }
};

onMounted(() => {
  // Request notification permission proactively (non-blocking)
  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }
  fetchStatus();
  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", onStatusPageVisible);
  }
  pollTimer = setInterval(() => {
    if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
    if (isLiveStatus.value) fetchStatus();
  }, POLL_INTERVAL_S * 1000);
});
onUnmounted(() => {
  clearInterval(pollTimer);
  stopCountdown();
  orderStore.clearPlacedOrder();
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", onStatusPageVisible);
  }
});
</script>
