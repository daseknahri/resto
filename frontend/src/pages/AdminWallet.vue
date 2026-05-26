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

    <!-- Loading / error -->
    <div v-if="loading" class="py-10 text-center text-sm text-slate-400">{{ t('common.loading') }}</div>
    <div v-else-if="fetchError" class="py-10 text-center text-sm text-red-300">{{ t('adminWallet.fetchError') }}</div>
    <div v-else-if="!customers.length" class="py-10 text-center text-sm text-slate-400">{{ t('adminWallet.empty') }}</div>

    <!-- Table -->
    <div v-else class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th class="px-4 py-3 text-left">#</th>
            <th class="px-4 py-3 text-left">{{ t('adminWallet.colName') }}</th>
            <th class="px-4 py-3 text-left">{{ t('adminWallet.colContact') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminWallet.colBalance') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminWallet.colActions') }}</th>
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
        >
          <div class="w-full max-w-sm rounded-2xl bg-slate-900 border border-slate-700 p-6 space-y-4">
            <h2 class="text-sm font-bold text-white">{{ t('adminWallet.bonusTitle') }}</h2>
            <p class="text-xs text-slate-400">
              {{ bonusTarget.name }}
              <span class="ml-2 text-slate-500">{{ t('adminWallet.currentBalance') }}: {{ fmtBalance(bonusTarget.wallet_balance) }}</span>
            </p>
            <div>
              <label class="block text-xs text-slate-400 mb-1">{{ t('adminWallet.bonusAmount') }}</label>
              <input
                v-model="bonusAmount"
                type="number"
                step="0.01"
                min="0.01"
                class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
                :placeholder="t('adminWallet.bonusAmountPlaceholder')"
              />
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">{{ t('adminWallet.bonusNote') }}</label>
              <input
                v-model="bonusNote"
                type="text"
                maxlength="200"
                class="w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
                :placeholder="t('adminWallet.bonusNotePlaceholder')"
              />
            </div>
            <p v-if="bonusError" class="text-xs text-red-400">{{ bonusError }}</p>
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
