<template>
  <div class="fixed inset-0 z-[3000] flex items-end justify-center bg-black/60 sm:items-center" @click.self="$emit('close')">
    <div class="w-full max-w-md rounded-t-3xl border border-slate-700 bg-slate-900 p-5 space-y-4 sm:rounded-2xl">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-white">{{ t('walletCharge.title') }}</h2>
        <button class="rounded-full p-1.5 text-slate-500 hover:text-slate-300" :aria-label="t('common.close')" @click="$emit('close')">✕</button>
      </div>

      <!-- Step 1: resolve a customer by pay code -->
      <template v-if="!customer">
        <p class="text-xs text-slate-400">{{ t('walletCharge.scanHint') }}</p>
        <div class="flex items-center gap-2">
          <button
            v-if="!scanning"
            class="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/8 px-3 py-1.5 text-sm font-semibold text-[var(--color-secondary)]"
            @click="beginScan"
          >
            <AppIcon name="qr" class="h-4 w-4" />{{ t('walletCharge.scan') }}
          </button>
          <button v-else class="rounded-full border border-slate-600 px-3 py-1.5 text-sm text-slate-300" @click="stop">{{ t('common.cancel') }}</button>
        </div>
        <div v-if="scanning" class="overflow-hidden rounded-xl border border-slate-700 bg-black">
          <video ref="videoEl" class="h-56 w-full object-cover" muted playsinline />
        </div>
        <div class="flex gap-2">
          <input v-model="manualToken" type="text" class="ui-input flex-1 text-sm" :placeholder="t('walletCharge.manualPlaceholder')" @keyup.enter="resolve(manualToken)" />
          <button class="shrink-0 rounded-xl border border-slate-600 px-4 py-2 text-sm text-slate-300 disabled:opacity-50" :disabled="!manualToken.trim() || resolving" @click="resolve(manualToken)">
            {{ t('walletCharge.find') }}
          </button>
        </div>
        <p v-if="error" class="text-xs text-red-300">{{ error }}</p>
      </template>

      <!-- Step 2a: waiting for the customer to approve an above-threshold charge -->
      <template v-else-if="awaiting">
        <div class="rounded-xl border border-slate-700/60 bg-slate-800/40 p-4 text-center space-y-2">
          <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-emerald-400"></div>
          <p class="text-sm font-semibold text-slate-100">{{ t('walletCharge.awaitingTitle', { amount: fmtMoney(awaiting.amount) }) }}</p>
          <p class="text-xs text-slate-400">{{ t('walletCharge.awaitingHint', { name: customer.name || customer.phone }) }}</p>
        </div>
        <button class="w-full rounded-xl border border-slate-600 px-4 py-2.5 text-sm text-slate-300" @click="cancelAwaiting">{{ t('common.cancel') }}</button>
      </template>

      <!-- Step 2b: charge the resolved customer -->
      <template v-else>
        <div class="rounded-xl border border-slate-700/60 bg-slate-800/40 p-3">
          <p class="text-sm font-semibold text-slate-100">{{ customer.name || customer.phone }}</p>
          <p class="text-xs text-slate-400">{{ t('walletCharge.balance') }}: <span class="font-semibold text-emerald-400">{{ fmtMoney(customer.wallet_balance) }}</span></p>
        </div>
        <label class="block text-xs font-semibold text-slate-300">
          {{ t('walletCharge.amount') }}
          <input v-model="amount" type="number" step="0.01" min="0.01" class="ui-input mt-1 w-full text-sm" :placeholder="t('walletCharge.amountPlaceholder')" />
        </label>
        <p v-if="error" class="text-xs text-red-300">{{ error }}</p>
        <div class="flex gap-2">
          <button class="rounded-xl border border-slate-600 px-4 py-2.5 text-sm text-slate-300" @click="reset">{{ t('walletCharge.back') }}</button>
          <button
            class="flex-1 rounded-xl bg-emerald-600 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
            :disabled="charging || !amount"
            @click="charge"
          >{{ charging ? '…' : t('walletCharge.charge') }}</button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue';
import AppIcon from './AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useToastStore } from '../stores/toast';
import { usePayCodeScanner } from '../composables/usePayCodeScanner';
import { newIdempotencyKey } from '../lib/idempotency';
import api from '../lib/api';

const props = defineProps({
  prefillAmount: { type: [String, Number], default: '' },
  orderNumber: { type: String, default: '' },
});
const emit = defineEmits(['close', 'charged']);
const { t, currentLocale } = useI18n();
const toast = useToastStore();
const { scanning, videoEl, start, stop } = usePayCodeScanner();

const manualToken = ref('');
const resolving = ref(false);
const customer = ref(null);
const amount = ref(props.prefillAmount ? String(props.prefillAmount) : '');
const charging = ref(false);
const error = ref('');
const awaiting = ref(null); // { request_id, amount } while waiting for customer approval
let chargeKey = null;
let pollTimer = null;
const POLL_MS = 2500;

const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
};

const startPolling = (requestId) => {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const { data } = await api.get(`/owner/wallet/charge-request/${requestId}/`);
      if (data.status === 'charged') {
        stopPolling();
        awaiting.value = null;
        toast.show(t('walletCharge.charged', { amount: fmtMoney(data.amount) }), 'success');
        emit('charged', data);
        emit('close');
      } else if (data.status === 'declined') {
        stopPolling();
        awaiting.value = null;
        error.value = t('walletCharge.declined');
      } else if (data.status === 'expired') {
        stopPolling();
        awaiting.value = null;
        error.value = t('walletCharge.requestExpired');
      }
      // pending → keep polling
    } catch {
      // transient error — keep polling until charged/declined/expired or cancelled
    }
  }, POLL_MS);
};

const cancelAwaiting = () => {
  stopPolling();
  awaiting.value = null; // back to the amount step; the request expires on its own TTL
};

onBeforeUnmount(stopPolling);

const fmtMoney = (v) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'MAD', maximumFractionDigits: 2 }).format(parseFloat(v || 0));
  } catch {
    return `${parseFloat(v || 0).toFixed(2)}`;
  }
};

const beginScan = async () => {
  error.value = '';
  const code = await start((token) => resolve(token));
  if (code === 'unsupported') error.value = t('walletCharge.scanUnsupported');
  else if (code === 'camera_failed') error.value = t('walletCharge.cameraFailed');
};

const resolve = async (token) => {
  const value = String(token || '').trim();
  if (!value) return;
  error.value = '';
  resolving.value = true;
  try {
    const { data } = await api.post('/owner/wallet/resolve-token/', { token: value });
    customer.value = data;
    customer.value.token = value; // reuse the same token for the charge
    manualToken.value = '';
    chargeKey = null;
  } catch (err) {
    error.value = err?.response?.data?.detail || t('walletCharge.resolveFailed');
  } finally {
    resolving.value = false;
  }
};

const reset = () => {
  stopPolling();
  awaiting.value = null;
  customer.value = null;
  amount.value = props.prefillAmount ? String(props.prefillAmount) : '';
  error.value = '';
};

const charge = async () => {
  error.value = '';
  const value = parseFloat(amount.value);
  if (!Number.isFinite(value) || value <= 0) { error.value = t('walletCharge.invalidAmount'); return; }
  charging.value = true;
  if (!chargeKey) chargeKey = newIdempotencyKey();
  try {
    const { data } = await api.post('/owner/wallet/charge/', {
      token: customer.value.token,
      amount: value.toFixed(2),
      order_number: props.orderNumber || '',
      idempotency_key: chargeKey,
    });
    if (data.status === 'pending') {
      // Above the approval threshold — wait for the customer to approve on their phone.
      awaiting.value = { request_id: data.request_id, amount: data.amount };
      charging.value = false;
      startPolling(data.request_id);
      return;
    }
    toast.show(t('walletCharge.charged', { amount: fmtMoney(data.amount) }), 'success');
    emit('charged', data);
    emit('close');
  } catch (err) {
    const d = err?.response?.data;
    if (d?.code === 'insufficient') {
      error.value = t('walletCharge.insufficient', { balance: fmtMoney(d.balance) });
    } else if (d?.code === 'expired') {
      error.value = t('walletCharge.expired');
      customer.value = null; // force a re-scan with a fresh code
    } else {
      error.value = d?.detail || t('walletCharge.chargeFailed');
    }
  } finally {
    charging.value = false;
  }
};
</script>
