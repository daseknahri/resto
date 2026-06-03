<template>
  <!-- Customer-confirmed charge: a restaurant is requesting an above-threshold debit.
       Mounted in CustomerLayout so it surfaces on ANY customer page, not just /account. -->
  <div v-if="activeCharge" class="fixed inset-0 z-[3500] flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-4">
    <div class="w-full max-w-sm rounded-t-3xl border border-slate-700 bg-slate-900 p-5 space-y-4 sm:rounded-2xl">
      <div class="text-center space-y-1">
        <p class="text-xs font-semibold uppercase tracking-wide text-amber-300">{{ t('chargeRequest.title') }}</p>
        <p class="text-3xl font-bold text-white">{{ formatPrice(activeCharge.amount) }}</p>
        <p class="text-sm text-slate-300">{{ t('chargeRequest.from', { name: activeCharge.restaurant_name || t('chargeRequest.aRestaurant') }) }}</p>
        <p v-if="activeCharge.order_number" class="text-xs text-slate-500">{{ t('chargeRequest.order', { num: activeCharge.order_number }) }}</p>
      </div>
      <div class="rounded-xl border border-slate-700/60 bg-slate-800/40 px-3 py-2 text-center text-xs text-slate-400">
        {{ t('chargeRequest.balanceLine', { balance: formatPrice(walletBalance) }) }}
      </div>
      <p v-if="chargeError" class="text-center text-xs text-red-300" role="alert">{{ chargeError }}</p>
      <div class="flex gap-2">
        <button
          class="flex-1 rounded-xl border border-slate-600 py-2.5 text-sm font-semibold text-slate-300 disabled:opacity-50"
          :disabled="!!chargeBusy"
          @click="declineCharge(activeCharge)"
        >{{ t('chargeRequest.decline') }}</button>
        <button
          class="flex-1 rounded-xl bg-emerald-600 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
          :disabled="!!chargeBusy"
          @click="approveCharge(activeCharge)"
        >{{ chargeBusy === activeCharge.id ? '…' : t('chargeRequest.approve') }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';

const { t, formatPrice } = useI18n();
const customerStore = useCustomerStore();
const toast = useToastStore();

const pendingCharges = ref([]);
const chargeBusy = ref(null);  // id of the request being approved/declined
const chargeError = ref('');
let pollTimer = null;
const POLL_MS = 5000;

const activeCharge = computed(() => pendingCharges.value[0] || null);
const walletBalance = computed(() => {
  const n = Number(customerStore.customer?.wallet_balance);
  return Number.isFinite(n) ? n : 0;
});

const fetchChargeRequests = async () => {
  if (!customerStore.isAuthenticated) return;
  try {
    const { data } = await api.get('/customer/wallet/charge-requests/');
    pendingCharges.value = Array.isArray(data?.requests) ? data.requests : [];
  } catch {
    /* transient — keep the last known list */
  }
};

const approveCharge = async (req) => {
  if (!req || chargeBusy.value) return;
  chargeBusy.value = req.id;
  chargeError.value = '';
  try {
    const { data } = await api.post(`/customer/wallet/charge-requests/${req.id}/approve/`);
    if (data?.new_balance !== undefined && customerStore.customer) {
      customerStore.setCustomer({ ...customerStore.customer, wallet_balance: data.new_balance });
    }
    pendingCharges.value = pendingCharges.value.filter((r) => r.id !== req.id);
    toast.show(t('chargeRequest.approved', { amount: formatPrice(req.amount) }), 'success');
  } catch (err) {
    const d = err?.response?.data;
    if (d?.code === 'insufficient') {
      chargeError.value = t('chargeRequest.insufficient', { balance: formatPrice(d.balance) });
    } else if (d?.code === 'expired') {
      chargeError.value = t('chargeRequest.expired');
      pendingCharges.value = pendingCharges.value.filter((r) => r.id !== req.id);
    } else {
      chargeError.value = d?.detail || t('chargeRequest.failed');
    }
  } finally {
    chargeBusy.value = null;
  }
};

const declineCharge = async (req) => {
  if (!req || chargeBusy.value) return;
  chargeBusy.value = req.id;
  chargeError.value = '';
  try {
    await api.post(`/customer/wallet/charge-requests/${req.id}/decline/`);
  } catch { /* drop locally even if the call fails */ }
  pendingCharges.value = pendingCharges.value.filter((r) => r.id !== req.id);
  chargeBusy.value = null;
};

const start = () => {
  stop();
  fetchChargeRequests();
  pollTimer = setInterval(fetchChargeRequests, POLL_MS);
};
const stop = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
};

watch(() => customerStore.isAuthenticated, (auth) => {
  if (auth) start();
  else { stop(); pendingCharges.value = []; }
});

onMounted(() => { if (customerStore.isAuthenticated) start(); });
onBeforeUnmount(stop);
</script>
