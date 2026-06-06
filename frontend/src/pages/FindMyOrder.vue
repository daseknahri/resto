<template>
  <div class="mx-auto max-w-lg space-y-4 px-3 py-3 pb-24 sm:px-4 sm:py-4">
    <!-- Header -->
    <div class="ui-hero-ribbon ui-reveal p-4 sm:p-5">
      <div class="space-y-1.5">
        <p class="ui-kicker">{{ t("orderStatus.kicker") }}</p>
        <h1 class="ui-display text-2xl font-semibold tracking-tight text-white">
          {{ t("orderStatus.findMyOrderTitle") }}
        </h1>
        <p class="ui-subtle">{{ t("orderStatus.findMyOrderSubtitle") }}</p>
      </div>
    </div>

    <!-- Search form -->
    <form class="ui-panel space-y-3 p-4" novalidate @submit.prevent="search">
      <div class="flex gap-2">
        <input
          v-model="phone"
          type="tel"
          inputmode="tel"
          autocomplete="tel"
          :aria-label="t('orderStatus.findMyOrderPhone')"
          :placeholder="t('orderStatus.findMyOrderPhone')"
          :disabled="loading"
          aria-required="true"
          class="ui-input flex-1 disabled:opacity-50"
          @keydown.enter.prevent="search"
        />
        <button
          type="submit"
          :disabled="loading || phone.replace(/\D/g, '').length < 6"
          :aria-busy="loading"
          class="ui-btn-primary ui-touch-target shrink-0 px-4 text-sm disabled:opacity-50"
        >
          {{ loading ? t("orderStatus.findMyOrderSearching") : t("orderStatus.findMyOrderSearch") }}
        </button>
      </div>
    </form>

    <!-- Error -->
    <div
      v-if="errorMsg"
      class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
      role="alert"
    >
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ errorMsg }}</p>
    </div>

    <!-- Loading skeleton -->
    <div v-else-if="loading" class="space-y-2" aria-live="polite" :aria-label="t('common.loading')">
      <div v-for="i in 3" :key="i" class="ui-skeleton h-20" />
    </div>

    <!-- No results -->
    <div
      v-else-if="searched && results.length === 0"
      class="ui-empty-state ui-reveal text-center"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        class="mx-auto mb-3 h-10 w-10 text-slate-600"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 15.803M10.5 7.5v6m3-3h-6" />
      </svg>
      <p class="text-sm font-semibold text-slate-100">{{ t("orderStatus.findMyOrderNoResults") }}</p>
      <p class="mt-1 text-xs text-slate-400">{{ t("orderStatus.findMyOrderSubtitle") }}</p>
    </div>

    <!-- Results -->
    <ul v-else-if="results.length" class="space-y-2">
      <li
        v-for="(order, index) in results"
        :key="order.order_number"
        class="ui-reveal"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <RouterLink
          :to="{ name: 'order-status', params: { orderNumber: order.order_number } }"
          class="ui-panel ui-surface-lift group relative flex items-center justify-between gap-3 overflow-hidden p-3.5 hover:border-[var(--color-secondary)]/30 hover:bg-slate-900/70 sm:p-4"
        >
          <!-- inline-start accent on hover (RTL-safe) -->
          <div
            class="pointer-events-none absolute inset-y-0 start-0 w-[3px] origin-top scale-y-0 rounded-s-xl transition-transform duration-200 group-hover:scale-y-100"
            style="background: linear-gradient(to bottom, rgba(245,158,11,0.6), rgba(245,158,11,0.1))"
          />
          <div class="min-w-0 space-y-1 ps-1">
            <p class="text-sm font-bold text-slate-100 tabular-nums">#{{ order.order_number }}</p>
            <p class="text-xs text-slate-500 tabular-nums">{{ formatDate(order.created_at) }}</p>
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
  out_for_delivery: () => t("orderStatus.stepOutForDelivery"),
  completed: () => t("orderStatus.statusCompleted"),
  cancelled: () => t("orderStatus.statusCancelled"),
};
const statusLabel = (s) => STATUS_LABEL[s]?.() ?? s;

const STATUS_CLASS = {
  pending: "bg-amber-500/20 text-amber-300",
  confirmed: "bg-blue-500/20 text-blue-300",
  preparing: "bg-orange-500/20 text-orange-300",
  ready: "bg-emerald-500/20 text-emerald-300",
  out_for_delivery: "bg-indigo-500/20 text-indigo-300",
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
