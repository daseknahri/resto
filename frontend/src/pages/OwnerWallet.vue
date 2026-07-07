<template>
  <div class="ui-page-shell space-y-4">
    <!-- Page header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-4 md:px-5 md:py-5">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="ui-kicker">{{ t('ownerWallet.kicker') }}</p>
          <h1 class="ui-display text-2xl font-bold leading-tight tracking-tight text-white md:text-3xl">
            {{ t('ownerWallet.title') }}
          </h1>
          <p class="ui-subtle mt-1">{{ t('ownerWallet.subtitle') }}</p>
        </div>
      </div>
    </header>

    <!-- Restaurant float card — how much the owner can still hand out -->
    <div class="ui-glass ui-reveal flex items-center justify-between gap-4 p-4 md:p-5" style="--ui-delay:40ms">
      <div class="min-w-0">
        <p class="ui-kicker mb-0.5">{{ t('ownerWallet.floatTitle') }}</p>
        <p class="mt-1 text-3xl font-bold tabular-nums tracking-tight text-emerald-400">
          <span v-if="loadingFloat" class="inline-block h-8 w-28 animate-pulse rounded-lg bg-slate-700/60 align-middle" />
          <span v-else>{{ fmtBalance(floatBalance) }}</span>
        </p>
        <p class="mt-1 text-xs text-slate-400">{{ t('ownerWallet.floatSubtitle') }}</p>
      </div>
      <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-emerald-500/10">
        <AppIcon name="wallet" class="h-6 w-6 text-emerald-400" aria-hidden="true" />
      </div>
    </div>

    <!-- Driver cash-out — confirm you handed a driver cash; it credits your float -->
    <section class="ui-panel ui-reveal space-y-3 p-4 md:p-5" style="--ui-delay:80ms">
      <div class="space-y-0.5">
        <p class="ui-kicker">{{ t('ownerWallet.driverCashoutTitle') }}</p>
        <p class="ui-subtle text-xs">{{ t('ownerWallet.driverCashoutHint') }}</p>
      </div>
      <div v-if="!cashoutPreview" class="flex gap-2">
        <input
          v-model.trim="cashoutCode"
          inputmode="numeric"
          maxlength="12"
          class="ui-input flex-1 py-2 text-sm"
          :placeholder="t('ownerWallet.driverCashoutCodePlaceholder')"
          :aria-label="t('ownerWallet.driverCashoutCodePlaceholder')"
        />
        <button
          class="ui-btn-outline ui-press ui-touch-target shrink-0 px-4 text-sm disabled:opacity-50"
          :disabled="!cashoutCode || cashoutBusy"
          @click="lookupCashout"
        >
          {{ t('ownerWallet.driverCashoutLookup') }}
        </button>
      </div>
      <div v-else class="space-y-3 rounded-xl border border-emerald-500/30 bg-emerald-500/8 p-4">
        <p class="text-sm font-medium text-slate-200">
          {{ t('ownerWallet.driverCashoutConfirmLine', { name: cashoutPreview.driver_name, amount: fmtBalance(cashoutPreview.amount) }) }}
        </p>
        <div class="flex gap-2">
          <button class="ui-btn-primary ui-press flex-1 py-2 text-sm disabled:opacity-50" :disabled="cashoutBusy" @click="confirmCashout">
            {{ t('ownerWallet.driverCashoutConfirm') }}
          </button>
          <button class="ui-btn-outline ui-press px-3 py-2 text-sm disabled:opacity-50" :disabled="cashoutBusy" @click="cashoutPreview = null">
            {{ t('common.cancel') }}
          </button>
        </div>
      </div>
      <div v-if="cashoutError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
        <p class="flex-1 text-xs text-red-300">{{ cashoutError }}</p>
      </div>
    </section>

    <!-- Scan pay code card -->
    <section class="ui-panel ui-reveal space-y-3 p-4 md:p-5" style="--ui-delay:120ms">
      <div class="flex items-center justify-between gap-2">
        <div class="space-y-0.5">
          <p class="ui-kicker">{{ t('ownerWallet.scanTitle') }}</p>
        </div>
        <button
          v-if="!scanning"
          class="ui-chip ui-press inline-flex items-center gap-1.5 border-[var(--color-secondary)]/40 bg-[var(--color-secondary)]/8 font-semibold text-[var(--color-secondary)]"
          @click="startScan"
        >
          <AppIcon name="qr" class="h-3.5 w-3.5" aria-hidden="true" />{{ t('ownerWallet.scanBtn') }}
        </button>
        <button v-else class="ui-btn-outline ui-press ui-touch-target px-3 text-xs" @click="stopScan">{{ t('common.cancel') }}</button>
      </div>

      <!-- Camera viewfinder -->
      <div v-if="scanning" class="overflow-hidden rounded-2xl border border-slate-700 bg-black">
        <p class="sr-only">{{ t('ownerWallet.scanTitle') }}</p>
        <video ref="videoEl" class="h-56 w-full object-cover" muted playsinline :aria-label="t('ownerWallet.scanTitle')" />
      </div>

      <!-- Manual entry fallback -->
      <div class="flex gap-2">
        <input
          v-model="manualToken"
          type="text"
          class="ui-input flex-1 text-sm"
          :placeholder="t('ownerWallet.scanManualPlaceholder')"
          :aria-label="t('ownerWallet.scanManualPlaceholder')"
          @keyup.enter="resolveToken(manualToken)"
        />
        <button
          class="ui-btn-outline ui-press ui-touch-target shrink-0 px-4 text-sm disabled:opacity-50"
          :disabled="!manualToken.trim()"
          @click="resolveToken(manualToken)"
        >
          {{ t('ownerWallet.scanFind') }}
        </button>
      </div>
      <div v-if="resolveError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
        <p class="flex-1 text-xs text-red-300">{{ resolveError }}</p>
      </div>
    </section>

    <!-- The two methods below are alternatives — scan the customer's code OR search by name -->
    <div class="flex items-center gap-3 px-2" aria-hidden="true">
      <div class="ui-divider flex-1" />
      <span class="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{{ t('ownerWallet.orSearch') }}</span>
      <div class="ui-divider flex-1" />
    </div>

    <!-- Customer search card -->
    <section class="ui-panel ui-reveal space-y-4 p-4 md:p-5" style="--ui-delay:160ms">
      <div class="space-y-0.5">
        <p class="ui-kicker">{{ t('ownerWallet.searchTitle') }}</p>
      </div>

      <!-- Search input -->
      <div class="relative">
        <AppIcon name="search" class="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
        <input
          v-model="searchQuery"
          type="text"
          :aria-label="t('ownerWallet.searchTitle')"
          class="ui-input w-full ps-10 pe-4 text-sm"
          :placeholder="t('ownerWallet.searchPlaceholder')"
          @input="onSearchInput"
        />
      </div>

      <!-- Search results: live region so screen readers announce arrivals -->
      <div aria-live="polite" aria-atomic="false">
        <!-- Loading: skeleton rows -->
        <div v-if="searching" class="space-y-2" aria-busy="true">
          <div v-for="i in 3" :key="i" class="flex animate-pulse items-center justify-between rounded-xl border border-slate-700/40 bg-slate-800/30 px-4 py-3.5">
            <div class="space-y-2">
              <div class="h-3.5 w-32 rounded bg-slate-700/60" />
              <div class="h-2.5 w-20 rounded bg-slate-800/50" />
            </div>
            <div class="h-4 w-16 rounded bg-slate-700/50" />
          </div>
        </div>
        <ul v-else-if="searchResults.length" class="space-y-1.5">
          <li
            v-for="(c, index) in searchResults"
            :key="c.id"
          >
            <button
              class="ui-surface-lift ui-reveal flex w-full items-center justify-between gap-3 rounded-xl border border-slate-700/50 bg-slate-800/40 px-4 py-3.5 text-left transition-colors hover:border-[var(--color-secondary)]/40 hover:bg-[var(--color-secondary)]/8"
              :class="selected?.id === c.id ? 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10' : ''"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
              :aria-pressed="selected?.id === c.id"
              @click="selectCustomer(c)"
            >
              <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-slate-100" :title="c.name">{{ c.name }}</p>
                <p class="mt-0.5 truncate text-xs text-slate-400" :title="c.phone || c.email || undefined">{{ c.phone || c.email || '' }}</p>
              </div>
              <span class="shrink-0 rounded-lg bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold tabular-nums text-emerald-400">
                {{ fmtBalance(c.wallet_balance) }}
              </span>
            </button>
          </li>
        </ul>
        <div v-else-if="searchQuery.length >= 2 && !searching" class="ui-empty-state space-y-1 p-6 text-center">
          <AppIcon name="search" class="mx-auto mb-2 h-8 w-8 text-slate-600" aria-hidden="true" />
          <p class="text-sm font-semibold text-slate-200">{{ t('ownerWallet.noResults') }}</p>
          <p class="text-xs text-slate-500">{{ t('ownerWallet.noResultsHint') }}</p>
        </div>
      </div>
    </section>

    <!-- Top-up form (shown when a customer is selected) -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 translate-y-2"
      leave-active-class="transition-all duration-150"
      leave-to-class="opacity-0 translate-y-2"
    >
      <section v-if="selected" class="ui-panel space-y-4 p-4 md:p-5">
        <!-- Selected customer summary -->
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0 space-y-0.5">
            <p class="truncate text-base font-semibold text-slate-100" :title="selected.name">{{ selected.name }}</p>
            <p class="text-xs text-slate-400">
              {{ t('ownerWallet.currentBalance') }}:
              <span class="font-semibold tabular-nums text-emerald-400">{{ fmtBalance(selected.wallet_balance) }}</span>
            </p>
          </div>
          <button
            class="ui-press rounded-full p-1.5 text-slate-500 transition-colors hover:bg-slate-800/60 hover:text-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
            :aria-label="t('common.close')"
            @click="selected = null"
          >
            <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div class="ui-divider" />

        <!-- Amount -->
        <div class="space-y-1.5">
          <label class="block text-xs font-semibold uppercase tracking-wide text-slate-400" for="topup-amount">
            {{ t('ownerWallet.amountLabel') }}
          </label>
          <div class="relative">
            <span class="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-slate-500" aria-hidden="true">{{ currency() }}</span>
            <input
              id="topup-amount"
              ref="topupAmountRef"
              v-model="topupAmount"
              type="number"
              step="0.01"
              min="0.01"
              class="ui-input w-full ps-12 pe-4 text-sm"
              :placeholder="t('ownerWallet.amountPlaceholder')"
            />
          </div>
        </div>

        <!-- Note -->
        <div class="space-y-1.5">
          <label class="block text-xs font-semibold uppercase tracking-wide text-slate-400" for="topup-note">
            {{ t('ownerWallet.noteLabel') }}
          </label>
          <input
            id="topup-note"
            v-model="topupNote"
            type="text"
            maxlength="200"
            class="ui-input w-full px-4 text-sm"
            :placeholder="t('ownerWallet.notePlaceholder')"
          />
          <p class="mt-1 text-end text-xs tabular-nums" :class="topupNote.length >= 160 ? 'text-amber-400' : 'text-slate-600'" aria-live="polite">{{ topupNote.length }}/200</p>
        </div>

        <div v-if="topupError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ topupError }}</p>
        </div>

        <button
          class="ui-btn-primary ui-press inline-flex w-full items-center justify-center gap-2 py-3 text-sm font-semibold disabled:opacity-50"
          :disabled="saving || !topupAmount"
          :aria-busy="saving"
          @click="doTopup"
        >
          <svg v-if="saving" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-3.5 w-3.5 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
          {{ saving ? t('ownerWallet.saving') : t('ownerWallet.topupBtn') }}
        </button>

        <!-- Transaction history -->
        <div class="space-y-3 border-t border-slate-700/40 pt-4">
          <p class="ui-kicker">{{ t('ownerWallet.historyTitle') }}</p>
          <div v-if="loadingHistory" class="space-y-2" aria-busy="true">
            <div v-for="i in 3" :key="i" class="flex animate-pulse items-center justify-between rounded-xl bg-slate-800/50 px-3 py-2.5">
              <div class="space-y-1.5">
                <div class="h-3 w-32 rounded bg-slate-700/60" />
                <div class="h-2.5 w-20 rounded bg-slate-700/40" />
              </div>
              <div class="h-3.5 w-16 rounded bg-slate-700/50" />
            </div>
          </div>
          <div v-else-if="!walletHistory.length" class="ui-empty-state rounded-xl border border-slate-700/30 p-5 text-center">
            <AppIcon name="wallet" class="mx-auto mb-2 h-7 w-7 text-slate-600" aria-hidden="true" />
            <p class="text-sm text-slate-400">{{ t('ownerWallet.historyEmpty') }}</p>
          </div>
          <ul v-else class="space-y-1.5">
            <li
              v-for="tx in walletHistory"
              :key="tx.id"
              class="flex items-center justify-between gap-3 rounded-xl border border-slate-700/30 bg-slate-800/30 px-3 py-2.5 text-xs"
            >
              <div class="min-w-0">
                <p class="truncate font-medium" :class="tx.type === 'payment' ? 'text-red-300' : 'text-slate-200'" :title="tx.note || tx.type || undefined">
                  {{ tx.note || tx.type }}
                </p>
                <p class="mt-0.5 text-[10px] text-slate-500">{{ fmtDate(tx.created_at) }}</p>
              </div>
              <span
                class="shrink-0 rounded-lg px-2 py-0.5 font-semibold tabular-nums"
                :class="tx.type === 'payment' ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'"
              >{{ tx.type === 'payment' ? '−' : '+' }}{{ fmtBalance(tx.amount) }}</span>
            </li>
          </ul>
        </div>
      </section>
    </Transition>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, nextTick, ref } from 'vue';
import { useRoute } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import { newIdempotencyKey } from '../lib/idempotency';

const { t, currentLocale } = useI18n();
const tenant = useTenantStore();
const toast = useToastStore();
const route = useRoute();

const searchQuery = ref('');
const searchResults = ref([]);
const searching = ref(false);
const selected = ref(null);
const topupAmount = ref('');
const topupNote = ref('');
const topupError = ref('');
const saving = ref(false);
// Stable across retries of the same top-up; cleared on success so the next one is fresh.
let topupKey = null;

// ── Restaurant float ────────────────────────────────────────────────────────────
const floatBalance = ref('0.00');
const loadingFloat = ref(true);

const fetchFloat = async () => {
  loadingFloat.value = true;
  try {
    const res = await api.get('/owner/wallet/float/');
    floatBalance.value = res.data?.float_balance ?? '0.00';
  } catch {
    /* leave previous value */
  } finally {
    loadingFloat.value = false;
  }
};

// ── Driver cash-out (confirm handing a driver cash for their wallet balance) ─────
const cashoutCode = ref('');
const cashoutPreview = ref(null);
const cashoutBusy = ref(false);
const cashoutError = ref('');
// Snapshot of the exact code that was looked up — confirm sends THIS, not the
// live cashoutCode binding, so a later autofill/paste/script mutation of the
// (hidden-but-still-bound) input can't redirect the payout to a different code.
let confirmedLookupCode = null;

const lookupCashout = async () => {
  cashoutError.value = '';
  cashoutBusy.value = true;
  const codeAtLookup = cashoutCode.value;
  try {
    const { data } = await api.get('/owner/driver-cashout/', { params: { code: codeAtLookup } });
    cashoutPreview.value = data;
    confirmedLookupCode = codeAtLookup; // snapshot only on a successful lookup
  } catch (err) {
    cashoutError.value = err?.response?.data?.detail || t('ownerWallet.driverCashoutNotFound');
  } finally {
    cashoutBusy.value = false;
  }
};

const confirmCashout = async () => {
  cashoutError.value = '';
  // Defense in depth: if the visible code field changed since lookup, the
  // preview is stale — force a fresh lookup rather than confirm a mismatched code.
  if (cashoutCode.value !== confirmedLookupCode) {
    cashoutPreview.value = null;
    confirmedLookupCode = null;
    cashoutError.value = t('ownerWallet.driverCashoutNotFound');
    return;
  }
  cashoutBusy.value = true;
  try {
    const { data } = await api.post('/owner/driver-cashout/confirm/', { code: confirmedLookupCode });
    toast.show(t('ownerWallet.driverCashoutPaid', { amount: fmtBalance(data.amount) }), 'success');
    cashoutPreview.value = null;
    cashoutCode.value = '';
    confirmedLookupCode = null;
    fetchFloat(); // float just went up by the cash-out
  } catch (err) {
    cashoutError.value = err?.response?.data?.detail || t('ownerWallet.driverCashoutFailed');
    cashoutPreview.value = null;
    confirmedLookupCode = null;
  } finally {
    cashoutBusy.value = false;
  }
};

// ── Wallet history ────────────────────────────────────────────────────────────
const walletHistory = ref([]);
const loadingHistory = ref(false);

let searchTimer = null;

const currency = () => tenant.resolvedMeta?.plan?.currency || 'MAD';

const fmtBalance = (bal) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency: currency(),
      maximumFractionDigits: 2,
    }).format(parseFloat(bal || 0));
  } catch {
    return `${parseFloat(bal || 0).toFixed(2)}`;
  }
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso.slice(0, 16);
  }
};

const onSearchInput = () => {
  clearTimeout(searchTimer);
  const q = searchQuery.value.trim();
  if (q.length < 2) {
    searchResults.value = [];
    return;
  }
  searchTimer = setTimeout(() => runSearch(q), 350);
};

const runSearch = async (q) => {
  searching.value = true;
  try {
    const res = await api.get('/owner/customers/', { params: { search: q } });
    // The owner/customers/ API returns { summary: {...}, customers: [...] }
    const raw = res.data?.customers || [];
    searchResults.value = raw
      .filter((c) => c.customer_id)
      .slice(0, 10)
      .map((c) => ({
        id: c.customer_id,
        name: c.name || `Customer #${c.customer_id}`,
        phone: c.phone || '',
        email: c.email || '',
        wallet_balance: c.wallet_balance || '0.00',
      }));
  } catch {
    searchResults.value = [];
  } finally {
    searching.value = false;
  }
};

const topupAmountRef = ref(null);

const selectCustomer = (c) => {
  selected.value = c;
  topupAmount.value = '';
  topupNote.value = '';
  topupError.value = '';
  topupKey = null; // fresh idempotency key for each new customer selection
  fetchHistory(c.id);
  // Move keyboard focus into the amount field once the top-up section renders (WCAG 2.4.3).
  nextTick(() => topupAmountRef.value?.focus());
};

// ── Scan pay code (QR) → resolve customer for a fast top-up ────────────────────
const scanning = ref(false);
const manualToken = ref('');
const resolveError = ref('');
const videoEl = ref(null);
let scanStream = null;
let scanRaf = null;

const resolveToken = async (token) => {
  const value = String(token || '').trim();
  if (!value) return;
  resolveError.value = '';
  try {
    const { data } = await api.post('/owner/wallet/resolve-token/', { token: value });
    manualToken.value = '';
    selectCustomer({ id: data.customer_id, name: data.name, phone: data.phone, wallet_balance: data.wallet_balance });
    toast.show(t('ownerWallet.scanResolved', { name: data.name || data.phone }), 'success');
  } catch (err) {
    resolveError.value = err?.response?.data?.detail || t('ownerWallet.scanFailed');
  }
};

const stopScan = () => {
  scanning.value = false;
  if (scanRaf) { cancelAnimationFrame(scanRaf); scanRaf = null; }
  if (scanStream) { scanStream.getTracks().forEach((tr) => tr.stop()); scanStream = null; }
};

const startScan = async () => {
  resolveError.value = '';
  if (!('BarcodeDetector' in window)) {
    resolveError.value = t('ownerWallet.scanUnsupported');
    return;
  }
  try {
    scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    scanning.value = true;
    await nextTick();
    if (!videoEl.value) { stopScan(); return; }
    videoEl.value.srcObject = scanStream;
    await videoEl.value.play();
    const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
    const loop = async () => {
      if (!scanning.value || !videoEl.value) return;
      try {
        const codes = await detector.detect(videoEl.value);
        if (codes && codes.length) {
          const token = codes[0].rawValue;
          stopScan();
          resolveToken(token);
          return;
        }
      } catch { /* keep scanning */ }
      scanRaf = requestAnimationFrame(loop);
    };
    scanRaf = requestAnimationFrame(loop);
  } catch {
    resolveError.value = t('ownerWallet.scanCameraFailed');
    stopScan();
  }
};

onBeforeUnmount(stopScan);

const fetchHistory = async (customerId) => {
  walletHistory.value = [];
  loadingHistory.value = true;
  try {
    const res = await api.get(`/owner/wallet/history/${customerId}/`);
    walletHistory.value = res.data.transactions || [];
  } catch {
    walletHistory.value = [];
  } finally {
    loadingHistory.value = false;
  }
};

const doTopup = async () => {
  topupError.value = '';
  const amount = parseFloat(topupAmount.value);
  if (!amount || amount <= 0) {
    topupError.value = t('ownerWallet.amountRequired');
    return;
  }
  saving.value = true;
  if (!topupKey) topupKey = newIdempotencyKey();
  try {
    const res = await api.post('/owner/wallet/topup/', {
      customer_id: selected.value.id,
      amount: amount.toFixed(2),
      note: topupNote.value.trim() || t('ownerWallet.defaultNote'),
      idempotency_key: topupKey,
    });
    // Update the displayed balance
    selected.value = { ...selected.value, wallet_balance: res.data.new_balance };
    // Also update in search results
    const idx = searchResults.value.findIndex((c) => c.id === selected.value.id);
    if (idx >= 0) searchResults.value[idx] = { ...searchResults.value[idx], wallet_balance: res.data.new_balance };
    // Reflect the float we just spent down (server returns the new float balance).
    if (res.data.float_balance != null) floatBalance.value = res.data.float_balance;
    topupKey = null; // confirmed — next top-up gets a fresh key
    topupAmount.value = '';
    topupNote.value = '';
    toast.show(t('ownerWallet.topupSuccess'));
    // Refresh transaction history
    fetchHistory(selected.value.id);
  } catch (err) {
    const data = err?.response?.data || {};
    // Insufficient float (402) returns the current float — sync the display to it.
    if (data.float_balance != null) floatBalance.value = data.float_balance;
    topupError.value = data.detail || t('ownerWallet.topupFailed');
  } finally {
    saving.value = false;
  }
};

onMounted(() => {
  fetchFloat();
  const q = (route.query.q || '').toString().trim();
  if (q.length >= 2) {
    searchQuery.value = q;
    runSearch(q);
  }
});
</script>
