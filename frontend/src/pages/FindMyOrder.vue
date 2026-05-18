<template>
  <div class="mx-auto max-w-lg space-y-4 px-3 py-6 pb-24 sm:px-4">
    <!-- Header -->
    <div class="space-y-1">
      <p class="ui-kicker">{{ t("orderStatus.kicker") }}</p>
      <h1 class="text-2xl font-semibold text-white">{{ t("orderStatus.findMyOrderTitle") }}</h1>
      <p class="text-sm text-slate-400">{{ t("orderStatus.findMyOrderSubtitle") }}</p>
    </div>

    <!-- Search form -->
    <form class="ui-panel flex gap-2 p-3" @submit.prevent="search">
      <input
        v-model="phone"
        type="tel"
        inputmode="tel"
        autocomplete="tel"
        :placeholder="t('orderStatus.findMyOrderPhone')"
        :disabled="loading"
        class="flex-1 rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-[var(--color-secondary)] focus:outline-none disabled:opacity-50"
        @keydown.enter.prevent="search"
      />
      <button
        type="submit"
        :disabled="loading || phone.replace(/\D/g, '').length < 6"
        class="ui-btn-primary shrink-0 px-4 py-2 text-sm disabled:opacity-50"
      >
        {{ loading ? t("orderStatus.findMyOrderSearching") : t("orderStatus.findMyOrderSearch") }}
      </button>
    </form>

    <!-- Error -->
    <div v-if="errorMsg" class="rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
      {{ errorMsg }}
    </div>

    <!-- No results -->
    <div v-else-if="searched && results.length === 0 && !loading" class="ui-panel p-6 text-center text-sm text-slate-400">
      {{ t("orderStatus.findMyOrderNoResults") }}
    </div>

    <!-- Results -->
    <ul v-else-if="results.length" class="space-y-2">
      <li v-for="order in results" :key="order.order_number">
        <RouterLink
          :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
          class="ui-panel flex items-center justify-between gap-3 p-3 hover:border-slate-600 transition-colors"
        >
          <div class="min-w-0 space-y-0.5">
            <p class="text-sm font-semibold text-slate-100">#{{ order.order_number }}</p>
            <p class="text-xs text-slate-500">{{ formatDate(order.created_at) }}</p>
            <p class="text-xs text-slate-400">
              {{ fulfillmentLabel(order.fulfillment_type) }}
              <span v-if="order.items_count"> · {{ order.items_count }} item{{ order.items_count !== 1 ? "s" : "" }}</span>
            </p>
          </div>
          <div class="flex shrink-0 flex-col items-end gap-1">
            <span
              class="rounded-full px-2.5 py-0.5 text-xs font-semibold"
              :class="statusClass(order.status)"
            >{{ statusLabel(order.status) }}</span>
            <span class="text-sm font-medium text-slate-300">{{ formatTotal(order) }}</span>
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

const { t } = useI18n();

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
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
  } catch {
    return iso;
  }
};

const formatTotal = (order) => {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: order.currency || "USD" }).format(
      parseFloat(order.total)
    );
  } catch {
    return `${order.total} ${order.currency}`;
  }
};
</script>
