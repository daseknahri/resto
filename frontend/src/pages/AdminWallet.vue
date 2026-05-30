<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminWallet.title') }}</h1>
        <p class="text-sm text-slate-400 mt-0.5">{{ t('adminWallet.subtitle') }}</p>
      </div>
    </div>

    <!-- Search + filter bar -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative flex-1 min-w-[200px]">
        <AppIcon name="search" class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          v-model="search"
          type="text"
          class="w-full rounded-xl border border-slate-700 bg-slate-800 py-2.5 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
          :placeholder="t('adminWallet.searchPlaceholder')"
          @input="onSearch"
        />
      </div>
      <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
        <input v-model="showZero" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" @change="fetch" />
        {{ t('adminWallet.showZero') }}
      </label>
      <button
        class="rounded-xl border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-sm text-slate-300 hover:border-slate-500 transition-colors"
        @click="fetch"
      >{{ t('adminWallet.refresh') }}</button>
    </div>

    <!-- Loading: skeleton table -->
    <div v-if="loading" class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-left">#</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminWallet.colName') }}</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminWallet.colContact') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminWallet.colBalance') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminWallet.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="i in 5" :key="i" class="animate-pulse">
            <td class="px-4 py-3"><div class="h-2.5 w-4 rounded bg-slate-700/60" /></td>
            <td class="px-4 py-3"><div class="h-3 w-24 rounded bg-slate-700/60" /></td>
            <td class="px-4 py-3"><div class="h-2.5 w-28 rounded bg-slate-800/60" /></td>
            <td class="px-4 py-3"><div class="ml-auto h-3 w-14 rounded bg-slate-800/50" /></td>
            <td class="px-4 py-3"><div class="ml-auto h-3 w-16 rounded bg-slate-800/40" /></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
      <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('adminWallet.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetch"
      >{{ t('common.retry') }}</button>
    </div>

    <div v-else-if="!customers.length" class="py-10 text-center text-sm text-slate-400">{{ t('adminWallet.empty') }}</div>

    <!-- Table -->
    <div v-else class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-left">#</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminWallet.colName') }}</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminWallet.colContact') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminWallet.colBalance') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminWallet.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="c in customers" :key="c.id" class="hover:bg-slate-800/30 transition-colors">
            <td class="px-4 py-3 text-slate-500 text-xs">{{ c.id }}</td>
            <td class="px-4 py-3 text-slate-200 font-medium">{{ c.name }}</td>
            <td class="px-4 py-3 text-slate-400 text-xs">{{ c.phone || c.email || '—' }}</td>
            <td class="px-4 py-3 text-right">
              <span
                class="font-semibold tabular-nums"
                :class="parseFloat(c.wallet_balance) > 0 ? 'text-emerald-400' : 'text-slate-500'"
              >{{ fmtBalance(c.wallet_balance) }}</span>
            </td>
            <td class="px-4 py-3 text-right">
              <button
                class="text-xs text-sky-400 hover:text-sky-300"
                @click="openBonus(c)"
              >{{ t('adminWallet.bonus') }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="flex items-center justify-between text-xs text-slate-400">
      <span>{{ t('adminWallet.showing', { from: (page - 1) * pageSize + 1, to: Math.min(page * pageSize, total), total }) }}</span>
      <div class="flex gap-2">
        <button
          class="rounded-lg border border-slate-700 px-3 py-1.5 hover:border-slate-500 disabled:opacity-40"
          :disabled="page <= 1"
          @click="changePage(page - 1)"
        >← {{ t('adminWallet.prev') }}</button>
        <button
          class="rounded-lg border border-slate-700 px-3 py-1.5 hover:border-slate-500 disabled:opacity-40"
          :disabled="page * pageSize >= total"
          @click="changePage(page + 1)"
        >{{ t('adminWallet.next') }} →</button>
      </div>
    </div>

    <!-- Create Vouchers section -->
    <div class="rounded-2xl border border-slate-700/60 bg-slate-800/30 p-5 space-y-4">
      <div>
        <h2 class="text-sm font-bold text-white">{{ t('adminWallet.voucherSectionTitle') }}</h2>
        <p class="text-xs text-slate-400 mt-0.5">{{ t('adminWallet.voucherSectionSubtitle') }}</p>
      </div>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <!-- Quantity -->
        <div>
          <label class="block text-xs text-slate-400 mb-1">
            {{ t('adminWallet.voucherQtyLabel') }}
            <input
              v-model="voucherQty"
              type="number"
              min="1"
              max="50"
              class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
            />
          </label>
        </div>
        <!-- Amount -->
        <div>
          <label class="block text-xs text-slate-400 mb-1">
            {{ t('adminWallet.voucherAmountLabel') }}
            <input
              v-model="voucherAmount"
              type="number"
              step="0.01"
              min="0.01"
              class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
              :placeholder="t('adminWallet.voucherAmountPlaceholder')"
            />
          </label>
        </div>
        <!-- Expiry -->
        <div>
          <label class="block text-xs text-slate-400 mb-1">
            {{ t('adminWallet.voucherExpiryLabel') }}
            <input
              v-model="voucherExpiry"
              type="datetime-local"
              class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
            />
          </label>
        </div>
        <!-- Note -->
        <div>
          <label class="block text-xs text-slate-400 mb-1">
            {{ t('adminWallet.voucherNoteLabel') }}
            <input
              v-model="voucherNote"
              type="text"
              maxlength="200"
              class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
              :placeholder="t('adminWallet.voucherNotePlaceholder')"
            />
          </label>
        </div>
      </div>
      <div v-if="voucherGenError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
        <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        <p class="flex-1 text-sm text-red-300">{{ voucherGenError }}</p>
      </div>
      <button
        class="rounded-full bg-[var(--color-secondary,#f59e0b)] px-5 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50 transition-opacity"
        :disabled="voucherGenerating"
        @click="generateVouchers"
      >{{ voucherGenerating ? t('adminWallet.voucherGenerating') : t('adminWallet.voucherGenerate') }}</button>

      <!-- Generated codes display -->
      <div v-if="generatedCodes.length" class="rounded-xl border border-emerald-700/40 bg-emerald-950/20 p-4 space-y-2">
        <div class="flex items-center justify-between">
          <p class="text-xs font-semibold text-emerald-400">{{ t('adminWallet.voucherCreatedTitle') }} ({{ generatedCodes.length }})</p>
          <button
            class="text-xs text-sky-400 hover:text-sky-300"
            @click="copyAllCodes"
          >{{ copiedAll ? t('adminWallet.voucherCopied') : t('adminWallet.voucherCopyAll') }}</button>
        </div>
        <div class="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
          <span
            v-for="code in generatedCodes"
            :key="code"
            class="rounded-lg border border-emerald-700/40 bg-emerald-900/30 px-2.5 py-1 font-mono text-xs text-emerald-300 select-all cursor-text"
          >{{ code }}</span>
        </div>
      </div>
    </div>

    <!-- Bonus modal -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-all duration-200"
        enter-from-class="opacity-0 translate-y-4"
        leave-active-class="transition-all duration-150"
        leave-to-class="opacity-0 translate-y-4"
      >
        <div
          v-if="bonusTarget"
          class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60"
          @click.self="bonusTarget = null"
          @keydown.esc.window="bonusTarget = null"
        >
          <div role="dialog" aria-modal="true" aria-labelledby="admin-wallet-bonus-dialog-title" class="w-full max-w-sm rounded-2xl bg-slate-900 border border-slate-700 p-6 space-y-4">
            <h2 id="admin-wallet-bonus-dialog-title" class="text-sm font-bold text-white">{{ t('adminWallet.bonusTitle') }}</h2>
            <p class="text-xs text-slate-400">
              {{ bonusTarget.name }}
              <span class="ml-2 text-slate-500">{{ t('adminWallet.currentBalance') }}: {{ fmtBalance(bonusTarget.wallet_balance) }}</span>
            </p>
            <div>
              <label class="block text-xs text-slate-400 mb-1">
                {{ t('adminWallet.bonusAmount') }}
                <input
                  v-model="bonusAmount"
                  type="number"
                  step="0.01"
                  min="0.01"
                  class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
                  :placeholder="t('adminWallet.bonusAmountPlaceholder')"
                />
              </label>
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">
                {{ t('adminWallet.bonusNote') }}
                <input
                  v-model="bonusNote"
                  type="text"
                  maxlength="200"
                  class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
                  :placeholder="t('adminWallet.bonusNotePlaceholder')"
                />
              </label>
            </div>
            <div v-if="bonusError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
              <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
              <p class="flex-1 text-sm text-red-300">{{ bonusError }}</p>
            </div>
            <div class="flex gap-3">
              <button
                class="flex-1 rounded-full bg-[var(--color-secondary,#f59e0b)] py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
                :disabled="bonusSaving"
                @click="issueBonus"
              >{{ bonusSaving ? '…' : t('adminWallet.bonusIssue') }}</button>
              <button
                class="rounded-full border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:border-slate-400"
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
import { useToastStore } from '../stores/toast';
import api from '../lib/api';

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

const generateVouchers = async () => {
  voucherGenError.value = '';
  const amount = parseFloat(voucherAmount.value);
  if (!amount || amount <= 0) {
    voucherGenError.value = t('adminWallet.voucherAmountRequired');
    return;
  }
  voucherGenerating.value = true;
  try {
    const payload = {
      count: Math.min(Math.max(parseInt(voucherQty.value, 10) || 1, 1), 50),
      amount: amount.toFixed(2),
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

// Bonus modal
const bonusTarget = ref(null);
const bonusAmount = ref('');
const bonusNote = ref('');
const bonusError = ref('');
const bonusSaving = ref(false);

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
    customers.value = res.data.results;
    total.value = res.data.total;
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
};

const issueBonus = async () => {
  bonusError.value = '';
  const amount = parseFloat(bonusAmount.value);
  if (!amount || amount <= 0) {
    bonusError.value = t('adminWallet.bonusAmountRequired');
    return;
  }
  bonusSaving.value = true;
  try {
    await api.post('/admin/wallet/bonus/', {
      customer_ids: [bonusTarget.value.id],
      amount: amount.toFixed(2),
      note: bonusNote.value.trim() || t('adminWallet.defaultNote'),
    });
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

onMounted(fetch);
</script>
