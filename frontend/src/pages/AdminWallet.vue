<template>
  <div class="ui-page-shell space-y-5">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t('adminWallet.kicker') }}</p>
          <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl">{{ t('adminWallet.title') }}</h1>
          <p class="ui-subtle mt-0.5 text-xs">{{ t('adminWallet.subtitle') }}</p>
        </div>
      </div>
    </header>

    <!-- Search + filter bar -->
    <div class="ui-toolbar-band">
      <div class="flex flex-wrap items-center gap-3">
        <div class="relative min-w-[180px] flex-1">
          <AppIcon name="search" class="absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
          <input
            v-model="search"
            type="text"
            class="ui-input ps-9"
            :aria-label="t('adminWallet.searchPlaceholder')"
            :placeholder="t('adminWallet.searchPlaceholder')"
            @input="onSearch"
          />
        </div>
        <label class="flex cursor-pointer items-center gap-2 text-sm text-slate-400">
          <input v-model="showZero" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" @change="fetch" />
          {{ t('adminWallet.showZero') }}
        </label>
        <button
          class="ui-btn-outline ui-press px-4 py-2"
          @click="fetch"
        >{{ t('adminWallet.refresh') }}</button>
      </div>
    </div>

    <!-- Loading: skeleton table -->
    <div v-if="loading" class="ui-table-wrap">
      <table class="w-full min-w-[36rem] text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-start">#</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t('adminWallet.colName') }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t('adminWallet.colContact') }}</th>
            <th scope="col" class="px-4 py-3 text-end">{{ t('adminWallet.colBalance') }}</th>
            <th scope="col" class="px-4 py-3 text-end">{{ t('adminWallet.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="i in 5" :key="i" class="animate-pulse">
            <td class="px-4 py-3"><div class="h-2.5 w-4 rounded bg-slate-700/60" /></td>
            <td class="px-4 py-3"><div class="h-3 w-24 rounded bg-slate-700/60" /></td>
            <td class="px-4 py-3"><div class="h-2.5 w-28 rounded bg-slate-800/60" /></td>
            <td class="px-4 py-3"><div class="ms-auto h-3 w-14 rounded bg-slate-800/50" /></td>
            <td class="px-4 py-3"><div class="ms-auto h-3 w-16 rounded bg-slate-800/40" /></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-red-300">{{ t('adminWallet.fetchError') }}</p>
      <button
        class="ui-btn-outline ui-press shrink-0 px-3 py-1 text-xs text-red-300 hover:border-red-500/40"
        @click="fetch"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!customers.length" class="ui-empty-state text-center p-6 space-y-1">
      <p class="text-sm font-semibold text-slate-100">{{ t('adminWallet.emptyTitle') }}</p>
      <p class="text-xs text-slate-400">{{ t('adminWallet.empty') }}</p>
    </div>

    <!-- Table -->
    <div v-else class="ui-table-wrap ui-reveal">
      <table class="w-full min-w-[36rem] text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-start">#</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t('adminWallet.colName') }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t('adminWallet.colContact') }}</th>
            <th scope="col" class="px-4 py-3 text-end">{{ t('adminWallet.colBalance') }}</th>
            <th scope="col" class="px-4 py-3 text-end">{{ t('adminWallet.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr
            v-for="c in customers"
            :key="c.id"
            class="transition-colors hover:bg-slate-800/30"
          >
            <td class="px-4 py-3 text-xs text-slate-500 tabular-nums">{{ c.id }}</td>
            <td class="px-4 py-3 font-medium text-slate-200">{{ c.name }}</td>
            <td class="px-4 py-3 text-xs text-slate-400">{{ c.phone || c.email || '—' }}</td>
            <td class="px-4 py-3 text-end">
              <span
                class="tabular-nums font-semibold"
                :class="parseFloat(c.wallet_balance) > 0 ? 'text-emerald-400' : 'text-slate-500'"
              ><span v-if="parseFloat(c.wallet_balance) > 0" aria-hidden="true">+</span>{{ fmtBalance(c.wallet_balance) }}</span>
            </td>
            <td class="px-4 py-3 text-end">
              <button
                class="ui-press rounded-lg px-2.5 py-1 text-xs font-medium text-[var(--color-primary)] hover:text-teal-300 ui-touch-target"
                @click="openBonus(c)"
              >{{ t('adminWallet.bonus') }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="flex items-center justify-between text-xs text-slate-400">
      <span class="tabular-nums">{{ t('adminWallet.showing', { from: (page - 1) * pageSize + 1, to: Math.min(page * pageSize, total), total }) }}</span>
      <div class="flex gap-2">
        <button
          class="ui-btn-outline ui-press px-3 py-1.5 text-xs disabled:opacity-40"
          :disabled="page <= 1"
          @click="changePage(page - 1)"
        ><span class="ltr:me-1 rtl:ms-1" aria-hidden="true">&#8592;</span>{{ t('adminWallet.prev') }}</button>
        <button
          class="ui-btn-outline ui-press px-3 py-1.5 text-xs disabled:opacity-40"
          :disabled="page * pageSize >= total"
          @click="changePage(page + 1)"
        >{{ t('adminWallet.next') }}<span class="ltr:ms-1 rtl:me-1" aria-hidden="true">&#8594;</span></button>
      </div>
    </div>

    <!-- Create Vouchers section -->
    <section class="ui-section-band ui-reveal p-5 space-y-4" :style="{ '--ui-delay': '60ms' }" aria-labelledby="voucher-section-title">
      <div>
        <p class="ui-kicker">{{ t('adminWallet.voucherKicker') }}</p>
        <h2 id="voucher-section-title" class="text-sm font-semibold text-white">{{ t('adminWallet.voucherSectionTitle') }}</h2>
        <p class="text-xs text-slate-400 mt-0.5">{{ t('adminWallet.voucherSectionSubtitle') }}</p>
      </div>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <!-- Quantity -->
        <div class="space-y-1">
          <label for="voucher-qty" class="block text-xs text-slate-400">{{ t('adminWallet.voucherQtyLabel') }}</label>
          <input
            id="voucher-qty"
            v-model="voucherQty"
            type="number"
            min="1"
            max="50"
            class="ui-input"
          />
        </div>
        <!-- Amount -->
        <div class="space-y-1">
          <label for="voucher-amount" class="block text-xs text-slate-400">{{ t('adminWallet.voucherAmountLabel') }}</label>
          <input
            id="voucher-amount"
            v-model="voucherAmount"
            type="number"
            step="0.01"
            min="0.01"
            class="ui-input"
            :placeholder="t('adminWallet.voucherAmountPlaceholder')"
          />
        </div>
        <!-- Expiry -->
        <div class="space-y-1">
          <label for="voucher-expiry" class="block text-xs text-slate-400">{{ t('adminWallet.voucherExpiryLabel') }}</label>
          <input
            id="voucher-expiry"
            v-model="voucherExpiry"
            type="datetime-local"
            class="ui-input"
          />
        </div>
        <!-- Note -->
        <div class="space-y-1">
          <label for="voucher-note" class="block text-xs text-slate-400">{{ t('adminWallet.voucherNoteLabel') }}</label>
          <input
            id="voucher-note"
            v-model="voucherNote"
            type="text"
            maxlength="200"
            class="ui-input"
            :placeholder="t('adminWallet.voucherNotePlaceholder')"
          />
        </div>
      </div>
      <div v-if="voucherGenError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
        <p class="flex-1 text-sm text-red-300">{{ voucherGenError }}</p>
      </div>
      <button
        class="ui-btn-primary disabled:opacity-50"
        :disabled="voucherGenerating"
        @click="generateVouchers"
      >{{ voucherGenerating ? t('adminWallet.voucherGenerating') : t('adminWallet.voucherGenerate') }}</button>

      <!-- Generated codes display -->
      <div v-if="generatedCodes.length" class="rounded-xl border border-emerald-700/40 bg-emerald-950/20 p-4 space-y-2">
        <div class="flex items-center justify-between gap-2">
          <p class="text-xs font-semibold text-emerald-400">{{ t('adminWallet.voucherCreatedTitle') }} ({{ generatedCodes.length }})</p>
          <button
            class="ui-press text-xs font-medium text-slate-300 hover:text-slate-100 ui-touch-target"
            @click="copyAllCodes"
          >{{ copiedAll ? t('adminWallet.voucherCopied') : t('adminWallet.voucherCopyAll') }}</button>
          <span role="status" aria-live="polite" class="sr-only">{{ copiedAll ? t('adminWallet.voucherCopied') : '' }}</span>
        </div>
        <div class="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
          <span
            v-for="code in generatedCodes"
            :key="code"
            class="cursor-text select-all rounded-lg border border-emerald-700/40 bg-emerald-900/30 px-2.5 py-1 font-mono text-xs text-emerald-300"
          >{{ code }}</span>
        </div>
      </div>

      <!-- Recent vouchers (audit created / redeemed) -->
      <div class="border-t border-slate-700/60 pt-4 space-y-2">
        <p class="ui-kicker">{{ t('adminWallet.voucherListTitle') }}</p>
        <div v-if="loadingVouchers" class="space-y-1.5">
          <div v-for="i in 3" :key="i" class="h-9 animate-pulse rounded-lg bg-slate-800/50" />
        </div>
        <div v-else-if="!vouchers.length" class="py-3 text-center text-xs text-slate-500 italic">{{ t('adminWallet.voucherListEmpty') }}</div>
        <ul v-else class="divide-y divide-slate-800/70 overflow-hidden rounded-xl border border-slate-700/60">
          <li v-for="v in vouchers" :key="v.code" class="flex items-center justify-between gap-3 bg-slate-900/40 px-3 py-2 text-xs">
            <div class="flex min-w-0 items-center gap-2.5">
              <span class="font-mono text-slate-200">{{ v.code }}</span>
              <span class="tabular-nums text-emerald-300">{{ fmtBalance(v.amount) }}</span>
            </div>
            <span
              class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold"
              :class="v.is_used ? 'bg-slate-700/60 text-slate-400' : 'bg-emerald-500/12 text-emerald-300'"
            >{{ v.is_used ? t('adminWallet.voucherUsed', { who: v.used_by_name || '' }) : t('adminWallet.voucherActive') }}</span>
          </li>
        </ul>
      </div>
    </section>

    <!-- Fund a restaurant float -->
    <section class="ui-panel p-5 space-y-4 ui-reveal" :style="{ '--ui-delay': '90ms' }" aria-labelledby="fund-section-title">
      <div>
        <p class="ui-kicker">{{ t('adminWallet.fundKicker') }}</p>
        <h2 id="fund-section-title" class="text-sm font-semibold text-white">{{ t('adminWallet.fundTitle') }}</h2>
        <p class="text-xs text-slate-400 mt-0.5">{{ t('adminWallet.fundSubtitle') }}</p>
      </div>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <!-- Restaurant -->
        <div class="space-y-1">
          <label for="fund-restaurant" class="block text-xs text-slate-400">{{ t('adminWallet.fundRestaurantLabel') }}</label>
          <select
            id="fund-restaurant"
            v-model="fundTenantId"
            class="ui-input"
          >
            <option value="">{{ t('adminWallet.fundSelectPlaceholder') }}</option>
            <option v-for="ten in fundTenants" :key="ten.id" :value="ten.id">
              {{ ten.name }} — {{ fmtBalance(ten.float_balance) }}
            </option>
          </select>
        </div>
        <!-- Amount -->
        <div class="space-y-1">
          <label for="fund-amount" class="block text-xs text-slate-400">{{ t('adminWallet.fundAmountLabel') }}</label>
          <input
            id="fund-amount"
            v-model="fundAmount"
            type="number"
            step="0.01"
            min="0.01"
            class="ui-input"
            :placeholder="t('adminWallet.fundAmountPlaceholder')"
          />
        </div>
        <!-- Note -->
        <div class="space-y-1">
          <label for="fund-note" class="block text-xs text-slate-400">{{ t('adminWallet.fundNoteLabel') }}</label>
          <input
            id="fund-note"
            v-model="fundNote"
            type="text"
            maxlength="200"
            class="ui-input"
            :placeholder="t('adminWallet.fundNotePlaceholder')"
          />
        </div>
      </div>
      <div v-if="fundError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
        <p class="flex-1 text-sm text-red-300">{{ fundError }}</p>
      </div>
      <button
        class="ui-btn-primary disabled:opacity-50"
        :disabled="fundSaving || !fundTenantId || !fundAmount"
        @click="fundFloat"
      >{{ fundSaving ? t('adminWallet.fundSaving') : t('adminWallet.fundBtn') }}</button>
    </section>

    <!-- Platform settings: wallet charge approval threshold -->
    <section class="ui-panel p-5 space-y-3 ui-reveal" :style="{ '--ui-delay': '120ms' }" aria-labelledby="settings-section-title">
      <div>
        <p class="ui-kicker">{{ t('adminWallet.settingsKicker') }}</p>
        <h2 id="settings-section-title" class="text-sm font-semibold text-white">{{ t('adminWallet.settingsTitle') }}</h2>
        <p class="text-xs text-slate-400 mt-0.5">{{ t('adminWallet.settingsSubtitle') }}</p>
      </div>
      <div class="flex flex-wrap items-end gap-3">
        <div class="space-y-1">
          <label for="threshold-input" class="block text-xs text-slate-400">{{ t('adminWallet.thresholdLabel') }}</label>
          <input
            id="threshold-input"
            v-model="threshold"
            type="number"
            step="0.01"
            min="0"
            class="ui-input w-40"
            :placeholder="t('adminWallet.thresholdPlaceholder')"
          />
        </div>
        <button
          class="ui-btn-outline ui-press disabled:opacity-50"
          :disabled="settingsSaving || threshold === ''"
          @click="saveSettings"
        >{{ settingsSaving ? t('adminWallet.thresholdSaving') : t('adminWallet.thresholdSave') }}</button>
      </div>
      <p class="text-[11px] text-slate-500">{{ t('adminWallet.thresholdHint') }}</p>
      <div v-if="settingsError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
        <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
        <p class="flex-1 text-sm text-red-300">{{ settingsError }}</p>
      </div>
    </section>

    <!-- Bonus modal -->
    <Teleport to="body">
      <Transition name="ui-fade">
        <div
          v-if="bonusTarget"
          class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          @click.self="bonusTarget = null"
        >
          <div
            ref="bonusDialogRef"
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-wallet-bonus-dialog-title"
            tabindex="-1"
            class="ui-panel w-full max-w-sm p-6 space-y-4"
            @keydown.esc="bonusTarget = null"
          >
            <h2 id="admin-wallet-bonus-dialog-title" class="text-sm font-semibold text-white">{{ t('adminWallet.bonusTitle') }}</h2>
            <p class="text-xs text-slate-400">
              {{ bonusTarget.name }}
              <span class="ms-2 text-slate-500 tabular-nums">{{ t('adminWallet.currentBalance') }}: {{ fmtBalance(bonusTarget.wallet_balance) }}</span>
            </p>
            <div class="space-y-1">
              <label for="bonus-amount" class="block text-xs text-slate-400">{{ t('adminWallet.bonusAmount') }}</label>
              <input
                id="bonus-amount"
                v-model="bonusAmount"
                type="number"
                step="0.01"
                min="0.01"
                class="ui-input"
                :placeholder="t('adminWallet.bonusAmountPlaceholder')"
              />
            </div>
            <div class="space-y-1">
              <label for="bonus-note" class="block text-xs text-slate-400">{{ t('adminWallet.bonusNote') }}</label>
              <input
                id="bonus-note"
                v-model="bonusNote"
                type="text"
                maxlength="200"
                class="ui-input"
                :placeholder="t('adminWallet.bonusNotePlaceholder')"
              />
            </div>
            <div v-if="bonusError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
              <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
              <p class="flex-1 text-sm text-red-300">{{ bonusError }}</p>
            </div>
            <div class="flex gap-3">
              <button
                class="ui-btn-primary flex-1 disabled:opacity-50"
                :disabled="bonusSaving || !bonusAmount"
                @click="issueBonus"
              >{{ bonusSaving ? t('adminWallet.bonusSaving') : t('adminWallet.bonusIssue') }}</button>
              <button
                class="ui-btn-outline ui-press px-4"
                @click="bonusTarget = null"
              >{{ t('adminWallet.cancel') }}</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useFocusTrap } from '../composables/useFocusTrap';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';
import adminApi from '../lib/adminApi';
import { newIdempotencyKey } from '../lib/idempotency';

const { t, currentLocale } = useI18n();
const toast = useToastStore();

const loading = ref(true);
const fetchError = ref(false);
const customers = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 50;
const search = ref('');
const showZero = ref(false);

// Voucher creation
const voucherQty = ref(1);
const voucherAmount = ref('');
const voucherExpiry = ref('');
const voucherNote = ref('');
const voucherGenerating = ref(false);
const voucherGenError = ref('');
const generatedCodes = ref([]);
const copiedAll = ref(false);
const vouchers = ref([]);
const loadingVouchers = ref(false);
let voucherKey = null; // stable across retries of the same voucher batch; cleared on success

const fetchVouchers = async () => {
  loadingVouchers.value = true;
  try {
    const res = await api.get('/admin/wallet/vouchers/');
    vouchers.value = res.data?.vouchers || res.data?.results || (Array.isArray(res.data) ? res.data : []);
  } catch {
    vouchers.value = [];
  } finally {
    loadingVouchers.value = false;
  }
};

const generateVouchers = async () => {
  voucherGenError.value = '';
  const amount = parseFloat(voucherAmount.value);
  if (!amount || amount <= 0) {
    voucherGenError.value = t('adminWallet.voucherAmountRequired');
    return;
  }
  voucherGenerating.value = true;
  if (!voucherKey) voucherKey = newIdempotencyKey();
  try {
    const payload = {
      count: Math.min(Math.max(parseInt(voucherQty.value, 10) || 1, 1), 50),
      amount: amount.toFixed(2),
      idempotency_key: voucherKey,
    };
    if (voucherNote.value.trim()) payload.note = voucherNote.value.trim();
    if (voucherExpiry.value) payload.expires_at = new Date(voucherExpiry.value).toISOString();
    const res = await api.post('/admin/wallet/vouchers/', payload);
    generatedCodes.value = res.data.codes || [];
    copiedAll.value = false;
    toast.show(t('adminWallet.voucherCreated', { count: res.data.created }));
    voucherAmount.value = '';
    voucherNote.value = '';
    voucherExpiry.value = '';
    voucherQty.value = 1;
    voucherKey = null; // confirmed — next batch gets a fresh key
    fetchVouchers(); // refresh the audit list with the new codes
  } catch (err) {
    const detail = err?.response?.data?.detail || '';
    voucherGenError.value = detail || t('adminWallet.voucherFailed');
  } finally {
    voucherGenerating.value = false;
  }
};

const copyAllCodes = async () => {
  try {
    await navigator.clipboard.writeText(generatedCodes.value.join('\n'));
    copiedAll.value = true;
    setTimeout(() => { copiedAll.value = false; }, 2000);
  } catch { /* ignore */ }
};

// Fund a restaurant float
const fundTenants = ref([]);
const fundTenantId = ref('');
const fundAmount = ref('');
const fundNote = ref('');
const fundError = ref('');
const fundSaving = ref(false);
let fundKey = null; // stable across retries of the same funding; cleared on success

const fetchTenants = async () => {
  try {
    const res = await adminApi.get('/admin-tenants/', { params: { page: 1, page_size: 200 } });
    const payload = res?.data;
    fundTenants.value = Array.isArray(payload) ? payload : (payload?.results || []);
  } catch {
    fundTenants.value = [];
  }
};

const fundFloat = async () => {
  fundError.value = '';
  const amount = parseFloat(fundAmount.value);
  if (!fundTenantId.value) {
    fundError.value = t('adminWallet.fundSelectRequired');
    return;
  }
  if (!amount || amount <= 0) {
    fundError.value = t('adminWallet.fundAmountRequired');
    return;
  }
  fundSaving.value = true;
  if (!fundKey) fundKey = newIdempotencyKey();
  try {
    const res = await adminApi.post('/admin/wallet/fund-tenant/', {
      tenant_id: fundTenantId.value,
      amount: amount.toFixed(2),
      note: fundNote.value.trim() || t('adminWallet.fundDefaultNote'),
      idempotency_key: fundKey,
    });
    // Reflect the new float on the selected tenant in the dropdown.
    const idx = fundTenants.value.findIndex((tn) => tn.id === fundTenantId.value);
    if (idx >= 0) fundTenants.value[idx] = { ...fundTenants.value[idx], float_balance: res.data.float_balance };
    fundKey = null; // confirmed — next funding gets a fresh key
    toast.show(t('adminWallet.fundSuccess'));
    fundAmount.value = '';
    fundNote.value = '';
  } catch (err) {
    const detail = err?.response?.data?.detail || '';
    fundError.value = detail || t('adminWallet.fundFailed');
  } finally {
    fundSaving.value = false;
  }
};

// Bonus modal
const bonusTarget = ref(null);
const bonusDialogRef = ref(null);
useFocusTrap(bonusDialogRef, bonusTarget);
const bonusAmount = ref('');
const bonusNote = ref('');
const bonusError = ref('');
const bonusSaving = ref(false);
let bonusKey = null; // idempotency key, stable across retries of the same bonus

let searchTimer = null;

const fmtBalance = (bal) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency: 'MAD',
      maximumFractionDigits: 2,
    }).format(parseFloat(bal || 0));
  } catch {
    return `${parseFloat(bal || 0).toFixed(2)}`;
  }
};

const fetch = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const params = {
      page: page.value,
      page_size: pageSize,
      min_balance: showZero.value ? 0 : 0.01,
    };
    if (search.value.trim()) params.search = search.value.trim();
    const res = await api.get('/admin/wallets/', { params });
    customers.value = res.data?.results || [];
    total.value = res.data?.total || 0;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const onSearch = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    page.value = 1;
    fetch();
  }, 400);
};

const changePage = (p) => {
  page.value = p;
  fetch();
};

const openBonus = (c) => {
  bonusTarget.value = c;
  bonusAmount.value = '';
  bonusNote.value = '';
  bonusError.value = '';
  bonusKey = null; // fresh idempotency key per bonus
};

const issueBonus = async () => {
  bonusError.value = '';
  const amount = parseFloat(bonusAmount.value);
  if (!amount || amount <= 0) {
    bonusError.value = t('adminWallet.bonusAmountRequired');
    return;
  }
  bonusSaving.value = true;
  if (!bonusKey) bonusKey = newIdempotencyKey();
  try {
    await api.post('/admin/wallet/bonus/', {
      customer_ids: [bonusTarget.value.id],
      amount: amount.toFixed(2),
      note: bonusNote.value.trim() || t('adminWallet.defaultNote'),
      idempotency_key: bonusKey,
    });
    bonusKey = null; // confirmed — next bonus gets a fresh key
    toast.show(t('adminWallet.bonusSuccess'));
    bonusTarget.value = null;
    fetch();
  } catch (err) {
    const detail = err?.response?.data?.detail || '';
    bonusError.value = detail || t('adminWallet.bonusFailed');
  } finally {
    bonusSaving.value = false;
  }
};

// ── Platform settings: wallet charge approval threshold ────────────────────────
const threshold = ref('');
const settingsSaving = ref(false);
const settingsError = ref('');

const fetchSettings = async () => {
  try {
    const res = await adminApi.get('/admin/settings/');
    threshold.value = res.data?.wallet_charge_approval_threshold ?? '';
  } catch { /* non-fatal — leave the field blank */ }
};

const saveSettings = async () => {
  settingsError.value = '';
  const val = parseFloat(threshold.value);
  if (!Number.isFinite(val) || val < 0) { settingsError.value = t('adminWallet.thresholdError'); return; }
  settingsSaving.value = true;
  try {
    const res = await adminApi.patch('/admin/settings/', { wallet_charge_approval_threshold: val.toFixed(2) });
    threshold.value = res.data?.wallet_charge_approval_threshold ?? threshold.value;
    toast.show(t('adminWallet.thresholdSaved'), 'success');
  } catch (err) {
    settingsError.value = err?.response?.data?.detail || t('adminWallet.thresholdError');
  } finally {
    settingsSaving.value = false;
  }
};

onMounted(() => {
  fetch();
  fetchTenants();
  fetchVouchers();
  fetchSettings();
});
</script>
