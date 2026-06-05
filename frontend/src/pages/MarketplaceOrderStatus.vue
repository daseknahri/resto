<template>
  <div class="min-h-screen bg-slate-950 px-4 py-8 pb-16">

    <!-- Screen-reader live region: announces order status changes -->
    <div
      v-if="order"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      class="sr-only"
    >{{ t(`mktOrderStatus.${order.status}`) }}</div>

    <!-- Back -->
    <div class="mx-auto max-w-md">
      <router-link to="/order" class="text-xs text-slate-400 hover:text-slate-200">
        {{ t('mktOrderStatus.backToMarketplace') }}
      </router-link>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !order" class="mx-auto max-w-md mt-6 space-y-4 animate-pulse">
      <div class="text-center space-y-2">
        <div class="mx-auto h-2.5 w-32 rounded bg-slate-700/60" />
        <div class="mx-auto h-5 w-48 rounded bg-slate-700/50" />
      </div>
      <!-- Status stepper skeleton -->
      <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
        <div class="flex items-center justify-between gap-1">
          <div v-for="i in 4" :key="i" class="flex flex-col items-center gap-1 flex-1">
            <div class="h-8 w-8 rounded-full bg-slate-700/60" />
            <div class="h-2 w-10 rounded bg-slate-800/50" />
          </div>
        </div>
      </div>
      <!-- Summary card skeleton -->
      <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5 space-y-3">
        <div v-for="i in 3" :key="i" class="flex justify-between">
          <div class="h-3 w-24 rounded bg-slate-700/60" />
          <div class="h-3 w-14 rounded bg-slate-800/50" />
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError && !order" role="alert" class="mx-auto max-w-sm mt-6">
      <div class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
        <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
        </svg>
        <p class="flex-1 text-sm text-red-300">{{ t('mktOrderStatus.loadError') }}</p>
        <button
          class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
          @click="fetchStatus"
        >{{ t('common.retry') }}</button>
      </div>
    </div>

    <div v-else-if="order" class="mx-auto max-w-md space-y-6 mt-6">

      <!-- Header -->
      <div class="text-center space-y-1">
        <p class="text-xs text-slate-500">{{ t('mktOrderStatus.restaurant', { name: order.restaurant_name }) }}</p>
        <h1 class="text-xl font-bold text-white">{{ t('mktOrderStatus.title', { number: order.order_number }) }}</h1>
        <p class="text-xs text-slate-500">{{ t('mktOrderStatus.trackingHint') }}</p>
      </div>

      <!-- Proof-of-delivery code (give it to your driver) -->
      <div
        v-if="order.delivery_code"
        class="rounded-2xl border border-indigo-400/50 bg-indigo-500/12 p-4 text-center"
      >
        <p class="text-xs font-semibold uppercase tracking-wider text-indigo-300">{{ t('mktOrderStatus.deliveryCodeTitle') }}</p>
        <p class="mt-1 text-3xl font-bold tracking-[0.3em] text-white">{{ order.delivery_code }}</p>
        <p class="mt-1 text-xs text-indigo-100/75">{{ t('mktOrderStatus.deliveryCodeHint') }}</p>
      </div>

      <!-- Scheduled (advance order) banner -->
      <div
        v-if="order.status === 'scheduled' && order.scheduled_for"
        class="rounded-2xl border border-violet-400/40 bg-violet-500/10 p-4 text-center"
      >
        <p class="text-2xl">🗓️</p>
        <p class="mt-1 text-sm font-semibold text-violet-100">{{ t('mktOrderStatus.scheduledFor', { time: formatScheduledFor(order.scheduled_for) }) }}</p>
      </div>

      <!-- Status stepper -->
      <div class="rounded-2xl border border-slate-800 bg-slate-900 p-5">
        <div class="flex items-center justify-between gap-1">
          <template v-for="(step, idx) in statusSteps" :key="step.key">
            <div class="flex flex-col items-center gap-1 flex-1">
              <div
                class="h-8 w-8 rounded-full border-2 flex items-center justify-center text-xs font-bold transition-colors"
                :class="stepClass(step.key)"
              >
                <span v-if="isStepDone(step.key)">✓</span>
                <span v-else-if="isCurrentStep(step.key)">●</span>
                <span v-else>{{ idx + 1 }}</span>
              </div>
              <span class="text-[9px] text-center leading-tight" :class="isCurrentStep(step.key) ? 'text-white font-semibold' : 'text-slate-500'">
                {{ t(`mktOrderStatus.${step.key}`) }}
              </span>
            </div>
            <!-- Connector -->
            <div
              v-if="idx < statusSteps.length - 1"
              class="h-0.5 flex-1 rounded mb-4 transition-colors"
              :class="isStepDone(statusSteps[idx + 1].key) || isCurrentStep(statusSteps[idx + 1].key) ? 'bg-emerald-500/60' : 'bg-slate-700'"
            />
          </template>
        </div>

        <!-- Current status label -->
        <p class="mt-4 text-center text-sm font-medium" :class="order.status === 'cancelled' ? 'text-red-400' : 'text-emerald-400'">
          {{ t(`mktOrderStatus.${order.status}`) }}
        </p>

        <!-- Self-cancel (early pickup/delivery orders only) -->
        <div v-if="order.can_cancel" class="mt-3 text-center">
          <button
            class="rounded-full border border-red-500/40 px-4 py-1.5 text-xs font-semibold text-red-300 transition-colors hover:bg-red-500/10 disabled:opacity-50"
            :disabled="cancelling"
            @click="cancelOrder"
          >
            {{ cancelling ? t('common.saving') : t('mktOrderStatus.cancelOrder') }}
          </button>
        </div>
      </div>

      <!-- Driver tracking panel (shared component) -->
      <DeliveryTracker :delivery="delivery" />


      <!-- Order items -->
      <div class="rounded-2xl border border-slate-800 bg-slate-900 p-4 space-y-3">
        <h2 class="text-sm font-semibold text-slate-300">{{ t('mktOrderStatus.yourItems') }}</h2>
        <div
          v-for="(item, idx) in order.items"
          :key="idx"
          class="flex justify-between gap-2 text-sm"
        >
          <span class="text-slate-300">{{ item.qty }}× {{ item.dish_name }}</span>
          <span class="shrink-0 text-slate-400">{{ fmtPrice(item.subtotal, order.currency) }}</span>
        </div>

        <!-- Totals -->
        <div class="border-t border-slate-800 pt-2 space-y-1 text-sm">
          <div v-if="Number(order.delivery_fee) > 0" class="flex justify-between text-slate-500">
            <span>{{ t('mktOrderStatus.deliveryFee') }}</span>
            <span>{{ fmtPrice(order.delivery_fee, order.currency) }}</span>
          </div>
          <div v-if="Number(order.loyalty_discount) > 0" class="flex justify-between text-amber-400/90">
            <span>{{ t('mktOrderStatus.loyaltyDiscount') }}</span>
            <span>−{{ fmtPrice(order.loyalty_discount, order.currency) }}</span>
          </div>
          <div v-if="Number(order.wallet_amount_paid) > 0" class="flex justify-between text-emerald-400/80">
            <span>{{ t('mktOrderStatus.walletPaid') }}</span>
            <span>−{{ fmtPrice(order.wallet_amount_paid, order.currency) }}</span>
          </div>
          <div class="flex justify-between font-bold text-white">
            <span>{{ t('mktOrderStatus.total') }}</span>
            <span>{{ fmtPrice(order.total, order.currency) }}</span>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import DeliveryTracker from '../components/DeliveryTracker.vue';

const { t, currentLocale } = useI18n();
const route = useRoute();
const toast = useToastStore();

const fmtPrice = (amount, currency) => {
  if (!currency) return Number(amount || 0).toFixed(2);
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency,
      maximumFractionDigits: 2,
    }).format(amount || 0);
  } catch {
    return `${Number(amount || 0).toFixed(2)} ${currency}`;
  }
};

const slug = route.params.slug;
const orderNumber = route.params.orderNumber;

const loading = ref(true);
const fetchError = ref(false);
const order = ref(null);

// ── Delivery tracking (driver card + live map rendered by <DeliveryTracker>) ─────
const delivery = ref(null);

const fetchDelivery = async () => {
  try {
    const res = await api.get(`/marketplace/track/${orderNumber}/`, {
      params: { restaurant: slug },
    });
    delivery.value = res.data;
  } catch {
    // 404 = no delivery job for this order, that's OK (pickup orders)
    delivery.value = null;
  }
};

// Driver rating now lives in <DeliveryTracker> (shared by both order pages).

const formatScheduledFor = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  try {
    return d.toLocaleString(undefined, {
      weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return d.toLocaleString();
  }
};

// ── Status stepper ────────────────────────────────────────────────────────────
const STATUS_ORDER = ['pending', 'confirmed', 'preparing', 'ready', 'out_for_delivery', 'completed'];
const statusSteps = [
  { key: 'pending' },
  { key: 'confirmed' },
  { key: 'preparing' },
  { key: 'ready' },
  { key: 'out_for_delivery' },
  { key: 'completed' },
];

const currentStatusIdx = computed(() => {
  if (!order.value) return -1;
  return STATUS_ORDER.indexOf(order.value.status);
});

const isCurrentStep = (key) => order.value?.status === key;
const isStepDone = (key) => {
  const keyIdx = STATUS_ORDER.indexOf(key);
  return keyIdx >= 0 && keyIdx < currentStatusIdx.value;
};

const stepClass = (key) => {
  if (order.value?.status === 'cancelled') {
    return key === 'cancelled'
      ? 'border-red-500 bg-red-500/20 text-red-300'
      : 'border-slate-700 text-slate-600';
  }
  if (isCurrentStep(key)) return 'border-emerald-500 bg-emerald-500/20 text-emerald-300';
  if (isStepDone(key)) return 'border-emerald-600/60 bg-emerald-900/40 text-emerald-500';
  return 'border-slate-700 text-slate-600';
};

// ── Polling ───────────────────────────────────────────────────────────────────
let _pollTimer = null;
const TERMINAL_STATUSES = new Set(['completed', 'cancelled']);

const fetchStatus = async () => {
  fetchError.value = false;
  try {
    const res = await api.get(`/marketplace/order/${orderNumber}/`, {
      params: { restaurant: slug },
    });
    order.value = res.data;
    // Stop polling when terminal
    if (TERMINAL_STATUSES.has(res.data.status)) {
      clearInterval(_pollTimer);
      _pollTimer = null;
    }
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const cancelling = ref(false);
const cancelOrder = async () => {
  if (cancelling.value) return;
  if (typeof window !== 'undefined' && !window.confirm(t('mktOrderStatus.cancelConfirm'))) return;
  cancelling.value = true;
  try {
    await api.post(`/marketplace/order/${orderNumber}/cancel/`, { restaurant: slug });
    toast.show(t('mktOrderStatus.cancelledOk'), 'success');
    await fetchStatus();
  } catch (err) {
    const code = err?.response?.data?.code;
    toast.show(code === 'cancel_too_late' ? t('mktOrderStatus.cancelTooLate') : t('mktOrderStatus.cancelFailed'), 'error');
  } finally {
    cancelling.value = false;
  }
};

const onMktStatusVisible = () => {
  if (document.visibilityState === 'visible' && _pollTimer) {
    fetchStatus();
    fetchDelivery();
  }
};

onMounted(() => {
  fetchStatus();
  fetchDelivery();
  document.addEventListener('visibilitychange', onMktStatusVisible);
  _pollTimer = setInterval(() => {
    if (document.visibilityState === 'hidden') return;
    fetchStatus();
    fetchDelivery();
  }, 10000);
});

onBeforeUnmount(() => {
  clearInterval(_pollTimer);
  document.removeEventListener('visibilitychange', onMktStatusVisible);
});
</script>
