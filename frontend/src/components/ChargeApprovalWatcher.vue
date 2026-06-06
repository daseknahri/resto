<template>
  <!-- Customer-confirmed charge: a restaurant is requesting an above-threshold debit.
       Mounted in CustomerLayout so it surfaces on ANY customer page, not just /account. -->
  <Transition name="ui-fade">
    <div
      v-if="activeCharge"
      class="fixed inset-0 z-[3500] flex items-end justify-center bg-black/75 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="`charge-title-${activeCharge.id}`"
    >
      <div class="ui-glass w-full max-w-sm space-y-4 rounded-t-[2rem] p-5 sm:rounded-[2rem] ui-reveal">
        <!-- Header -->
        <div class="space-y-1 text-center">
          <p class="ui-kicker" style="color: var(--color-secondary);">{{ t('chargeRequest.title') }}</p>
          <p
            :id="`charge-title-${activeCharge.id}`"
            class="tabular-nums text-3xl font-bold tracking-tight text-white"
          >{{ formatPrice(activeCharge.amount) }}</p>
          <p class="ui-subtle">{{ t('chargeRequest.from', { name: activeCharge.restaurant_name || t('chargeRequest.aRestaurant') }) }}</p>
          <p v-if="activeCharge.order_number" class="text-xs text-slate-500">{{ t('chargeRequest.order', { num: activeCharge.order_number }) }}</p>
        </div>

        <!-- Balance band -->
        <div class="ui-context-band px-3 py-2 text-center text-xs text-slate-400">
          <span class="tabular-nums">{{ t('chargeRequest.balanceLine', { balance: formatPrice(walletBalance) }) }}</span>
        </div>

        <!-- Error -->
        <div
          v-if="chargeError"
          class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
          role="alert"
        >
          <svg class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
          </svg>
          <p class="flex-1 text-sm text-red-300">{{ chargeError }}</p>
        </div>

        <!-- Actions -->
        <div class="flex gap-2">
          <button
            class="ui-btn-outline ui-press ui-touch-target flex-1 text-sm font-semibold disabled:pointer-events-none disabled:opacity-50"
            :disabled="!!chargeBusy"
            @click="declineCharge(activeCharge)"
          >{{ t('chargeRequest.decline') }}</button>
          <button
            class="ui-btn-primary ui-press ui-touch-target flex-1 text-sm disabled:pointer-events-none disabled:opacity-50"
            :disabled="!!chargeBusy"
            :aria-busy="chargeBusy === activeCharge.id"
            @click="approveCharge(activeCharge)"
          >{{ chargeBusy === activeCharge.id ? '…' : t('chargeRequest.approve') }}</button>
        </div>
      </div>
    </div>
  </Transition>
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
