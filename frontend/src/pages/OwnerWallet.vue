<template>
  <div class="space-y-6 pb-6">
    <!-- Page header -->
    <div class="space-y-0.5">
      <p class="ui-kicker">{{ t('ownerWallet.kicker') }}</p>
      <h1 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ t('ownerWallet.title') }}</h1>
      <p class="text-sm text-slate-400">{{ t('ownerWallet.subtitle') }}</p>
    </div>

    <!-- Customer search card -->
    <div class="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-5 space-y-4">
      <p class="text-sm font-semibold text-slate-200">{{ t('ownerWallet.searchTitle') }}</p>

      <!-- Search input -->
      <div class="relative">
        <AppIcon name="search" class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          v-model="searchQuery"
          type="text"
          class="w-full rounded-xl border border-slate-700 bg-slate-800 py-2.5 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
          :placeholder="t('ownerWallet.searchPlaceholder')"
          @input="onSearchInput"
        />
      </div>

      <!-- Search results loading: skeleton rows -->
      <div v-if="searching" class="space-y-1.5">
        <div v-for="i in 3" :key="i" class="flex animate-pulse items-center justify-between rounded-xl border border-slate-700/40 bg-slate-800/30 px-4 py-3">
          <div class="space-y-1.5">
            <div class="h-3.5 w-28 rounded bg-slate-700/60" />
            <div class="h-2.5 w-20 rounded bg-slate-800/50" />
          </div>
          <div class="h-4 w-14 rounded bg-slate-700/50" />
        </div>
      </div>
      <div v-else-if="searchResults.length" class="space-y-1.5">
        <button
          v-for="c in searchResults"
          :key="c.id"
          class="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-700/50 bg-slate-800/40 px-4 py-3 text-left hover:border-indigo-500/40 hover:bg-indigo-500/8 transition-colors"
          :class="selected?.id === c.id ? 'border-indigo-500/50 bg-indigo-500/10' : ''"
          @click="selectCustomer(c)"
        >
          <div class="min-w-0">
            <p class="truncate text-sm font-medium text-slate-100">{{ c.name }}</p>
            <p class="text-xs text-slate-500">{{ c.phone || c.email || '' }}</p>
          </div>
          <span class="shrink-0 text-xs font-semibold text-emerald-400">
            {{ fmtBalance(c.wallet_balance) }}
          </span>
        </button>
      </div>
      <p v-else-if="searchQuery.length >= 2 && !searching" class="text-sm text-slate-500 py-2">
        {{ t('ownerWallet.noResults') }}
      </p>
    </div>

    <!-- Top-up form (shown when a customer is selected) -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 translate-y-2"
      leave-active-class="transition-all duration-150"
      leave-to-class="opacity-0 translate-y-2"
    >
      <div v-if="selected" class="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-5 space-y-4">
        <!-- Selected customer summary -->
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="text-sm font-semibold text-slate-100">{{ selected.name }}</p>
            <p class="text-xs text-slate-400">
              {{ t('ownerWallet.currentBalance') }}:
              <span class="font-semibold text-emerald-400">{{ fmtBalance(selected.wallet_balance) }}</span>
            </p>
          </div>
          <button
            class="rounded-full p-1.5 text-slate-500 hover:text-slate-300 transition-colors"
            :aria-label="t('common.close')"
            @click="selected = null"
          >
            <AppIcon name="close" class="h-4 w-4" />
          </button>
        </div>

        <div class="border-t border-slate-700/40" />

        <!-- Amount -->
        <div>
          <label class="block text-xs font-semibold text-slate-300 mb-1.5">
            {{ t('ownerWallet.amountLabel') }}
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-slate-500">+</span>
              <input
                v-model="topupAmount"
                type="number"
                step="0.01"
                min="0.01"
                class="w-full rounded-xl border border-slate-700 bg-slate-800 py-2.5 pl-7 pr-4 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
                :placeholder="t('ownerWallet.amountPlaceholder')"
              />
            </div>
          </label>
        </div>

        <!-- Note -->
        <div>
          <label class="block text-xs font-semibold text-slate-300 mb-1.5">
            {{ t('ownerWallet.noteLabel') }}
            <input
              v-model="topupNote"
              type="text"
              maxlength="200"
              class="w-full rounded-xl border border-slate-700 bg-slate-800 py-2.5 px-4 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
              :placeholder="t('ownerWallet.notePlaceholder')"
            />
          </label>
        </div>

        <div v-if="topupError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5">
          <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
          <p class="flex-1 text-sm text-red-300">{{ topupError }}</p>
        </div>

        <button
          class="w-full rounded-xl bg-emerald-600 py-2.5 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
          :disabled="saving || !topupAmount"
          @click="doTopup"
        >
          {{ saving ? t('ownerWallet.saving') : t('ownerWallet.topupBtn') }}
        </button>

        <!-- Transaction history -->
        <div class="border-t border-slate-700/40 pt-4 space-y-2">
          <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">{{ t('ownerWallet.historyTitle') }}</p>
          <div v-if="loadingHistory" class="space-y-1.5">
            <div v-for="i in 3" :key="i" class="h-8 animate-pulse rounded-lg bg-slate-800/50" />
          </div>
          <p v-else-if="!walletHistory.length" class="text-xs text-slate-600 italic">{{ t('ownerWallet.historyEmpty') }}</p>
          <ul v-else class="space-y-1">
            <li
              v-for="tx in walletHistory"
              :key="tx.id"
              class="flex items-center justify-between gap-2 rounded-lg bg-slate-800/30 px-3 py-2 text-xs"
            >
              <div class="min-w-0">
                <p class="font-medium" :class="tx.type === 'payment' ? 'text-red-300' : 'text-slate-200'">
                  {{ tx.note || tx.type }}
                </p>
                <p class="text-[10px] text-slate-600">{{ fmtDate(tx.created_at) }}</p>
              </div>
              <span
                class="shrink-0 font-semibold tabular-nums"
                :class="tx.type === 'payment' ? 'text-red-400' : 'text-emerald-400'"
              >{{ tx.type === 'payment' ? '−' : '+' }}{{ fmtBalance(tx.amount) }}</span>
            </li>
          </ul>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useTenantStore } from '../stores/tenant';
import { useToastStore } from '../stores/toast';
import api from '../lib/api';

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

const selectCustomer = (c) => {
  selected.value = c;
  topupAmount.value = '';
  topupNote.value = '';
  topupError.value = '';
  fetchHistory(c.id);
};

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
  try {
    const res = await api.post('/owner/wallet/topup/', {
      customer_id: selected.value.id,
      amount: amount.toFixed(2),
      note: topupNote.value.trim() || t('ownerWallet.defaultNote'),
    });
    // Update the displayed balance
    selected.value = { ...selected.value, wallet_balance: res.data.new_balance };
    // Also update in search results
    const idx = searchResults.value.findIndex((c) => c.id === selected.value.id);
    if (idx >= 0) searchResults.value[idx] = { ...searchResults.value[idx], wallet_balance: res.data.new_balance };
    topupAmount.value = '';
    topupNote.value = '';
    toast.show(t('ownerWallet.topupSuccess'));
    // Refresh transaction history
    fetchHistory(selected.value.id);
  } catch (err) {
    const detail = err?.response?.data?.detail || '';
    topupError.value = detail || t('ownerWallet.topupFailed');
  } finally {
    saving.value = false;
  }
};

onMounted(() => {
  const q = (route.query.q || '').toString().trim();
  if (q.length >= 2) {
    searchQuery.value = q;
    runSearch(q);
  }
});
</script>
