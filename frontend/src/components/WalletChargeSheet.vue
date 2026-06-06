<template>
  <div
    class="fixed inset-0 z-[3000] flex items-end justify-center bg-black/60 sm:items-center"
    role="dialog"
    aria-modal="true"
    :aria-labelledby="'wallet-charge-title'"
    @click.self="$emit('close')"
  >
    <div class="ui-panel-soft ui-reveal w-full max-w-md space-y-4 rounded-t-3xl p-5 sm:rounded-3xl">
      <!-- Header -->
      <div class="flex items-center justify-between gap-3">
        <h2 id="wallet-charge-title" class="text-base font-semibold text-white">
          {{ t('walletCharge.title') }}
        </h2>
        <button
          class="ui-btn-outline ui-press flex h-8 w-8 shrink-0 items-center justify-center rounded-full p-0"
          :aria-label="t('common.close')"
          @click="$emit('close')"
        >
          <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <!-- Step 1: resolve a customer by pay code -->
      <template v-if="!customer">
        <p class="ui-subtle text-xs">{{ t('walletCharge.scanHint') }}</p>

        <!-- Scan / cancel row -->
        <div class="flex items-center gap-2">
          <button
            v-if="!scanning"
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-4 text-sm font-semibold text-[var(--color-secondary)]"
            @click="beginScan"
          >
            <AppIcon name="qr" class="h-4 w-4" aria-hidden="true" />
            {{ t('walletCharge.scan') }}
          </button>
          <button
            v-else
            class="ui-btn-outline ui-press ui-touch-target px-4 text-sm"
            @click="stop"
          >
            {{ t('common.cancel') }}
          </button>
        </div>

        <!-- Camera viewfinder -->
        <div v-if="scanning" class="ui-reveal overflow-hidden rounded-2xl border border-slate-700/70 bg-black">
          <video ref="videoEl" class="h-56 w-full object-cover" muted playsinline />
        </div>

        <!-- Manual token row -->
        <div class="flex gap-2">
          <input
            v-model="manualToken"
            type="text"
            class="ui-input flex-1 text-sm"
            :placeholder="t('walletCharge.manualPlaceholder')"
            @keyup.enter="resolve(manualToken)"
          />
          <button
            class="ui-btn-outline ui-press ui-touch-target shrink-0 px-4 text-sm disabled:opacity-50"
            :disabled="!manualToken.trim() || resolving"
            @click="resolve(manualToken)"
          >
            {{ t('walletCharge.find') }}
          </button>
        </div>

        <!-- Error -->
        <div
          v-if="error"
          class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
          role="alert"
        >
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ error }}</p>
        </div>
      </template>

      <!-- Step 2a: waiting for the customer to approve an above-threshold charge -->
      <template v-else-if="awaiting">
        <div class="ui-panel space-y-3 p-4 text-center">
          <!-- Reduced-motion-safe pulsing indicator -->
          <div
            class="mx-auto h-8 w-8 rounded-full border-2 border-slate-600 border-t-emerald-400 motion-safe:animate-spin"
            aria-hidden="true"
          />
          <p class="text-sm font-semibold text-slate-100 tabular-nums">
            {{ t('walletCharge.awaitingTitle', { amount: fmtMoney(awaiting.amount) }) }}
          </p>
          <p class="ui-subtle text-xs">
            {{ t('walletCharge.awaitingHint', { name: customer.name || customer.phone }) }}
          </p>
        </div>
        <button
          class="ui-btn-outline ui-press ui-touch-target w-full text-sm"
          @click="cancelAwaiting"
        >
          {{ t('common.cancel') }}
        </button>
      </template>

      <!-- Step 2b: charge the resolved customer -->
      <template v-else>
        <!-- Customer info card -->
        <div class="ui-panel flex items-center gap-3 p-3">
          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-semibold text-slate-100">{{ customer.name || customer.phone }}</p>
            <p class="text-xs text-slate-400">
              {{ t('walletCharge.balance') }}:
              <span class="font-semibold tabular-nums text-emerald-400">{{ fmtMoney(customer.wallet_balance) }}</span>
            </p>
          </div>
        </div>

        <!-- Amount field -->
        <label class="block space-y-1" :for="'wc-amount'">
          <span class="ui-kicker">{{ t('walletCharge.amount') }}</span>
          <input
            id="wc-amount"
            v-model="amount"
            type="number"
            step="0.01"
            min="0.01"
            class="ui-input w-full text-sm tabular-nums"
            :placeholder="t('walletCharge.amountPlaceholder')"
          />
        </label>

        <!-- Error -->
        <div
          v-if="error"
          class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
          role="alert"
        >
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ error }}</p>
        </div>

        <!-- Actions -->
        <div class="flex gap-2">
          <button
            class="ui-btn-outline ui-press ui-touch-target px-4 text-sm"
            @click="reset"
          >
            {{ t('walletCharge.back') }}
          </button>
          <button
            class="ui-btn-primary ui-press ui-touch-target flex-1 text-sm disabled:opacity-50"
            :disabled="charging || !amount"
            @click="charge"
          >
            {{ charging ? t('common.loading') : t('walletCharge.charge') }}
          </button>
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
