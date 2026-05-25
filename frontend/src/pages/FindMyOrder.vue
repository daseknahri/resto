<template>
  <div class="mx-auto max-w-lg space-y-4 px-3 py-3 pb-24 sm:px-4 sm:py-4">
    <!-- Header -->
    <div class="ui-hero-ribbon ui-reveal p-4 sm:p-5">
      <div class="space-y-1.5">
        <p class="ui-kicker">{{ t("orderStatus.kicker") }}</p>
        <h1 class="ui-display text-2xl font-semibold tracking-tight text-white">{{ t("orderStatus.findMyOrderTitle") }}</h1>
        <p class="text-sm text-slate-400">{{ t("orderStatus.findMyOrderSubtitle") }}</p>
      </div>
    </div>

    <!-- Search form -->
    <form class="ui-panel space-y-3 p-4" @submit.prevent="search">
      <div class="flex gap-2">
        <input
          v-model="phone"
          type="tel"
          inputmode="tel"
          autocomplete="tel"
          :placeholder="t('orderStatus.findMyOrderPhone')"
          :disabled="loading"
          class="ui-input flex-1 disabled:opacity-50"
          @keydown.enter.prevent="search"
        />
        <button
          type="submit"
          :disabled="loading || phone.replace(/\D/g, '').length < 6"
          class="ui-btn-primary shrink-0 px-4 py-2.5 text-sm disabled:opacity-50"
        >
          {{ loading ? t("orderStatus.findMyOrderSearching") : t("orderStatus.findMyOrderSearch") }}
        </button>
      </div>
    </form>

    <!-- Error -->
    <div v-if="errorMsg" class="rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      {{ errorMsg }}
    </div>

    <!-- No results -->
    <div v-else-if="searched && results.length === 0 && !loading" class="ui-panel p-8 text-center space-y-2">
      <p class="text-3xl">🔍</p>
      <p class="text-sm font-medium text-slate-300">{{ t("orderStatus.findMyOrderNoResults") }}</p>
      <p class="text-xs text-slate-500">{{ t("orderStatus.findMyOrderSubtitle") }}</p>
    </div>

    <!-- Results -->
    <ul v-else-if="results.length" class="space-y-2">
      <li v-for="order in results" :key="order.order_number">
        <RouterLink
          :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
          class="ui-panel group relative flex items-center justify-between gap-3 overflow-hidden p-3.5 transition-all duration-200 hover:border-[var(--color-secondary)]/30 hover:bg-slate-900/70 sm:p-4"
        >
          <!-- left accent on hover -->
          <div class="pointer-events-none absolute inset-y-0 left-0 w-[3px] origin-left scale-y-0 rounded-l-xl transition-transform duration-200 group-hover:scale-y-100" style="background: linear-gradient(to bottom, rgba(245,158,11,0.6), rgba(245,158,11,0.1))" />
          <div class="min-w-0 space-y-1 pl-1">
            <p class="text-sm font-bold text-slate-100 tabular-nums">#{{ order.order_number }}</p>
            <p class="text-xs text-slate-500">{{ formatDate(order.created_at) }}</p>
            <p class="text-xs text-slate-400">
              {{ fulfillmentLabel(order.fulfillment_type) }}
              <span v-if="order.items_count"> · {{ t("orderStatus.findMyOrderItems", { count: order.items_count }) }}</span>
            </p>
          </div>
          <div class="flex shrink-0 flex-col items-end gap-1.5">
            <span
              class="rounded-full px-2.5 py-0.5 text-xs font-semibold"
              :class="statusClass(order.status)"
            >{{ statusLabel(order.status) }}</span>
            <span class="text-sm font-semibold tabular-nums text-[var(--color-secondary)]">{{ formatTotal(order) }}</span>
          </div>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useI18n } from "../composables/useI18n";
import api from "../lib/api";

const { t, formatPrice, currentLocale } = useI18n();

const phone = ref("");
const loading = ref(false);
const searched = ref(false);
const results = ref([]);
const errorMsg = ref("");

const search = async () => {
  const digits = phone.value.replace(/\D/g, "");
  if (digits.length < 6) return;
  loading.value = true;
  searched.value = false;
  errorMsg.value = "";
  results.value = [];
  try {
    const res = await api.get(`/orders/by-phone/?phone=${encodeURIComponent(phone.value)}`);
    results.value = res.data?.results || [];
    searched.value = true;
  } catch (err) {
    const code = err?.response?.data?.code;
    if (code === "rate_limited") {
      errorMsg.value = t("orderStatus.findMyOrderRateLimit");
    } else if (code === "phone_too_short") {
      errorMsg.value = t("orderStatus.findMyOrderPhoneTooShort");
    } else {
      errorMsg.value = t("orderStatus.findMyOrderError");
    }
  } finally {
    loading.value = false;
  }
};

const STATUS_LABEL = {
  pending: () => t("orderStatus.statusPending"),
  confirmed: () => t("orderStatus.statusConfirmed"),
  preparing: () => t("orderStatus.statusPreparing"),
  ready: () => t("orderStatus.statusReady"),
  completed: () => t("orderStatus.statusCompleted"),
  cancelled: () => t("orderStatus.statusCancelled"),
};
const statusLabel = (s) => STATUS_LABEL[s]?.() ?? s;

const STATUS_CLASS = {
  pending: "bg-amber-500/20 text-amber-300",
  confirmed: "bg-blue-500/20 text-blue-300",
  preparing: "bg-violet-500/20 text-violet-300",
  ready: "bg-emerald-500/20 text-emerald-300",
  completed: "bg-slate-700 text-slate-400",
  cancelled: "bg-red-500/20 text-red-300",
};
const statusClass = (s) => STATUS_CLASS[s] ?? "bg-slate-700 text-slate-400";

const fulfillmentLabel = (type) => {
  if (type === "delivery") return t("orderStatus.fulfillmentDelivery");
  if (type === "table") return t("orderStatus.tableOrderLabel");
  return t("orderStatus.fulfillmentPickup");
};

const formatDate = (iso) => {
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const formatTotal = (order) => formatPrice(parseFloat(order.total) || 0);
</script>
