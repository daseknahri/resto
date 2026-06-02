<template>
  <div class="p-6 space-y-6">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminCustomers.title') }}</h1>
        <p class="mt-0.5 text-sm text-slate-400">{{ t('adminCustomers.subtitle') }}</p>
      </div>
      <span v-if="!loading" class="shrink-0 rounded-full border border-slate-700 bg-slate-800/60 px-3 py-1 text-xs text-slate-300">
        {{ t('adminCustomers.totalLabel', { count: total }) }}
      </span>
    </div>

    <!-- Search + filters -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative flex-1 min-w-[200px]">
        <AppIcon name="search" class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          v-model="search"
          type="text"
          class="w-full rounded-xl border border-slate-700 bg-slate-800 py-2.5 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
          :aria-label="t('adminCustomers.searchPlaceholder')"
          :placeholder="t('adminCustomers.searchPlaceholder')"
          @input="onSearch"
        />
      </div>
      <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
        <input v-model="verifiedOnly" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" @change="reload" />
        {{ t('adminCustomers.filterVerified') }}
      </label>
      <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
        <input v-model="driversOnly" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" @change="reload" />
        {{ t('adminCustomers.filterDrivers') }}
      </label>
      <button
        class="rounded-xl border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-sm text-slate-300 hover:border-slate-500 disabled:opacity-50 transition-colors"
        :disabled="loading"
        @click="reload"
      >{{ loading ? '…' : t('adminCustomers.refresh') }}</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="overflow-hidden rounded-2xl border border-slate-700/60">
      <div v-for="i in 6" :key="i" class="flex items-center gap-4 border-b border-slate-800/60 px-4 py-3">
        <div class="h-3 w-32 animate-pulse rounded bg-slate-700/60" />
        <div class="ml-auto h-3 w-16 animate-pulse rounded bg-slate-800/50" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <p class="flex-1 text-sm text-red-300">{{ t('adminCustomers.fetchError') }}</p>
      <button class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10" @click="reload">
        {{ t('common.retry') }}
      </button>
    </div>

    <!-- Empty -->
    <div v-else-if="!customers.length" class="py-10 text-center text-sm text-slate-400">{{ t('adminCustomers.empty') }}</div>

    <!-- Table -->
    <div v-else class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminCustomers.colCustomer') }}</th>
            <th scope="col" class="px-4 py-3 text-left">{{ t('adminCustomers.colContact') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminCustomers.colWallet') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminCustomers.colLoyalty') }}</th>
            <th scope="col" class="px-4 py-3 text-right">{{ t('adminCustomers.colJoined') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="c in customers" :key="c.id" class="cursor-pointer hover:bg-slate-800/30 transition-colors" @click="openDetail(c)">
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span class="font-medium text-slate-200">{{ c.name || t('adminCustomers.unnamed') }}</span>
                <span v-if="c.is_driver" class="rounded-full bg-emerald-500/12 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">{{ t('adminCustomers.driver') }}</span>
              </div>
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-col gap-0.5">
                <span class="flex items-center gap-1.5 text-slate-300">
                  {{ c.phone || '—' }}
                  <span v-if="c.phone && c.phone_verified" class="text-[10px] text-emerald-400">✓</span>
                </span>
                <span v-if="c.email" class="text-xs text-slate-500">{{ c.email }}</span>
              </div>
            </td>
            <td class="px-4 py-3 text-right">
              <span class="font-semibold tabular-nums" :class="parseFloat(c.wallet_balance) > 0 ? 'text-emerald-400' : 'text-slate-500'">
                {{ fmtMoney(c.wallet_balance) }}
              </span>
            </td>
            <td class="px-4 py-3 text-right tabular-nums text-slate-300">{{ c.loyalty_points }}</td>
            <td class="px-4 py-3 text-right text-xs text-slate-500">{{ fmtDate(c.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="!loading && total > pageSize" class="flex items-center justify-between text-xs text-slate-400">
      <span>{{ t('adminCustomers.showing', { from: (page - 1) * pageSize + 1, to: Math.min(page * pageSize, total), total }) }}</span>
      <div class="flex gap-2">
        <button class="rounded-lg border border-slate-700 px-3 py-1.5 hover:border-slate-500 disabled:opacity-40" :disabled="page <= 1" @click="changePage(page - 1)">← {{ t('adminCustomers.prev') }}</button>
        <button class="rounded-lg border border-slate-700 px-3 py-1.5 hover:border-slate-500 disabled:opacity-40" :disabled="page * pageSize >= total" @click="changePage(page + 1)">{{ t('adminCustomers.next') }} →</button>
      </div>
    </div>

    <!-- Customer detail slide-over -->
    <Teleport to="body">
      <Transition enter-active-class="transition-opacity duration-200" enter-from-class="opacity-0" leave-active-class="transition-opacity duration-150" leave-to-class="opacity-0">
        <div v-if="selected" class="fixed inset-0 z-50 bg-black/60" @click.self="selected = null">
          <Transition enter-active-class="transition-transform duration-200" enter-from-class="translate-x-full" leave-active-class="transition-transform duration-150" leave-to-class="translate-x-full">
            <aside v-if="selected" class="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto border-l border-slate-700 bg-slate-900 p-5 space-y-5">
              <!-- Header -->
              <div class="flex items-start justify-between gap-3">
                <div>
                  <h2 class="text-lg font-semibold text-white">{{ selected.name || t('adminCustomers.unnamed') }}</h2>
                  <p class="text-xs text-slate-500">{{ selected.phone || selected.email || ('#' + selected.id) }}</p>
                </div>
                <button class="rounded-full p-1.5 text-slate-500 hover:text-slate-300" :aria-label="t('common.close')" @click="selected = null">
                  <AppIcon name="close" class="h-4 w-4" />
                </button>
              </div>

              <div v-if="loadingDetail" class="space-y-3">
                <div v-for="i in 4" :key="i" class="h-12 animate-pulse rounded-xl bg-slate-800/50" />
              </div>

              <template v-else-if="detail">
                <!-- Summary tiles -->
                <div class="grid grid-cols-2 gap-3">
                  <div class="rounded-xl border border-slate-700/60 bg-slate-800/30 p-3">
                    <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('adminCustomers.colWallet') }}</p>
                    <p class="text-lg font-bold tabular-nums text-emerald-400">{{ fmtMoney(detail.wallet_balance) }}</p>
                  </div>
                  <div class="rounded-xl border border-slate-700/60 bg-slate-800/30 p-3">
                    <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('adminCustomers.trust') }}</p>
                    <p class="text-lg font-bold tabular-nums text-slate-200">
                      {{ detail.trust.avg_score != null ? detail.trust.avg_score + ' ★' : t('adminCustomers.trustNone') }}
                      <span v-if="detail.trust.count" class="text-xs font-normal text-slate-500">({{ detail.trust.count }})</span>
                    </p>
                  </div>
                </div>
                <div class="flex flex-wrap gap-2 text-[11px]">
                  <span class="rounded-full px-2 py-0.5" :class="detail.phone_verified ? 'bg-emerald-500/12 text-emerald-300' : 'bg-slate-700/60 text-slate-400'">{{ detail.phone_verified ? t('adminCustomers.verified') : t('adminCustomers.unverified') }}</span>
                  <span class="rounded-full bg-slate-700/60 px-2 py-0.5 text-slate-300">{{ t('adminCustomers.colLoyalty') }}: {{ detail.loyalty_points }}</span>
                  <span v-if="detail.is_driver" class="rounded-full bg-sky-500/12 px-2 py-0.5 text-sky-300">{{ t('adminCustomers.driver') }} · {{ detail.delivery_jobs }}</span>
                </div>

                <!-- Driver toggle -->
                <button
                  class="w-full rounded-xl border px-4 py-2 text-sm transition-colors disabled:opacity-50"
                  :class="detail.is_driver ? 'border-slate-600 text-slate-300 hover:border-slate-400' : 'border-sky-500/40 text-sky-300 hover:border-sky-400/70'"
                  :disabled="togglingDriver"
                  @click="toggleDriver"
                >{{ detail.is_driver ? t('adminCustomers.removeDriver') : t('adminCustomers.makeDriver') }}</button>

                <!-- Credit wallet -->
                <div class="rounded-xl border border-slate-700/60 bg-slate-800/30 p-3 space-y-2.5">
                  <p class="text-sm font-semibold text-slate-200">{{ t('adminCustomers.creditTitle') }}</p>
                  <div class="flex gap-2">
                    <input v-model="creditAmount" type="number" step="0.01" min="0.01" class="ui-input flex-1 text-sm" :placeholder="t('adminCustomers.creditAmount')" />
                    <button class="shrink-0 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-50" :disabled="crediting || !creditAmount" @click="creditWallet">
                      {{ crediting ? '…' : t('adminCustomers.creditBtn') }}
                    </button>
                  </div>
                  <input v-model="creditNote" type="text" maxlength="200" class="ui-input w-full text-sm" :placeholder="t('adminCustomers.creditNote')" />
                  <p v-if="creditError" class="text-xs text-red-300">{{ creditError }}</p>
                </div>

                <!-- Cross-restaurant ledger -->
                <div class="space-y-2">
                  <p class="text-xs font-semibold uppercase tracking-wider text-slate-400">{{ t('adminCustomers.ledgerTitle') }}</p>
                  <p v-if="!detail.transactions.length" class="py-3 text-center text-xs text-slate-600 italic">{{ t('adminCustomers.ledgerEmpty') }}</p>
                  <ul v-else class="space-y-1.5">
                    <li v-for="tx in detail.transactions" :key="tx.id" class="flex items-center justify-between gap-2 rounded-lg bg-slate-800/30 px-3 py-2 text-xs">
                      <div class="min-w-0">
                        <p class="font-medium" :class="isOutflow(tx.type) ? 'text-red-300' : 'text-slate-200'">
                          {{ txLabel(tx.type) }}<span v-if="tx.tenant_name" class="text-slate-500"> · {{ tx.tenant_name }}</span>
                        </p>
                        <p class="text-[10px] text-slate-600">{{ tx.reference || '' }} {{ fmtDate(tx.created_at) }}</p>
                      </div>
                      <span class="shrink-0 font-semibold tabular-nums" :class="isOutflow(tx.type) ? 'text-red-400' : 'text-emerald-400'">
                        {{ isOutflow(tx.type) ? '−' : '+' }}{{ fmtMoney(tx.amount) }}
                      </span>
                    </li>
                  </ul>
                </div>
              </template>
            </aside>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import { newIdempotencyKey } from '../lib/idempotency';

const { t, currentLocale } = useI18n();

const loading = ref(true);
const fetchError = ref(false);
const customers = ref([]);
const total = ref(0);
const page = ref(1);
const pageSize = 25;
const search = ref('');
const verifiedOnly = ref(false);
const driversOnly = ref(false);
let searchTimer = null;

const fmtMoney = (v) => {
  try {
    return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'MAD', maximumFractionDigits: 2 })
      .format(parseFloat(v || 0));
  } catch {
    return `${parseFloat(v || 0).toFixed(2)}`;
  }
};

const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { dateStyle: 'medium' }).format(new Date(iso));
  } catch {
    return iso.slice(0, 10);
  }
};

const fetchCustomers = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const params = { page: page.value, page_size: pageSize };
    if (search.value.trim()) params.search = search.value.trim();
    if (verifiedOnly.value) params.verified_only = 1;
    if (driversOnly.value) params.drivers_only = 1;
    const res = await api.get('/admin/customers/', { params });
    customers.value = res.data?.results || [];
    total.value = res.data?.total || 0;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const reload = () => {
  page.value = 1;
  fetchCustomers();
};

const onSearch = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(reload, 400);
};

const changePage = (p) => {
  page.value = p;
  fetchCustomers();
};

// ── Detail slide-over + admin actions ───────────────────────────────────────
const selected = ref(null);
const detail = ref(null);
const loadingDetail = ref(false);
const creditAmount = ref('');
const creditNote = ref('');
const crediting = ref(false);
const creditError = ref('');
let creditKey = null;
const togglingDriver = ref(false);

const TX_KEY = {
  topup: 'customerAccount.walletTxTopup',
  payment: 'customerAccount.walletTxPayment',
  refund: 'customerAccount.walletTxRefund',
  bonus: 'customerAccount.walletTxBonus',
  loyalty: 'customerAccount.walletTxLoyalty',
  transfer_in: 'customerAccount.walletTxTransferIn',
  transfer_out: 'customerAccount.walletTxTransferOut',
  adjustment: 'adminCustomers.txAdjustment',
};
const txLabel = (type) => t(TX_KEY[type] || 'customerAccount.walletTxFallback');
const isOutflow = (type) => type === 'payment' || type === 'transfer_out';

const openDetail = async (c) => {
  selected.value = c;
  detail.value = null;
  creditAmount.value = '';
  creditNote.value = '';
  creditError.value = '';
  creditKey = null;
  loadingDetail.value = true;
  try {
    const res = await api.get(`/admin/customers/${c.id}/`);
    detail.value = res.data;
  } catch {
    creditError.value = t('adminCustomers.fetchError');
  } finally {
    loadingDetail.value = false;
  }
};

const syncRow = (patch) => {
  const row = customers.value.find((c) => c.id === selected.value?.id);
  if (row) Object.assign(row, patch);
};

const creditWallet = async () => {
  creditError.value = '';
  const amount = parseFloat(creditAmount.value);
  if (!amount || amount <= 0) { creditError.value = t('adminCustomers.creditFailed'); return; }
  crediting.value = true;
  if (!creditKey) creditKey = newIdempotencyKey();
  try {
    const res = await api.post(`/admin/customers/${selected.value.id}/credit/`, {
      amount: amount.toFixed(2),
      note: creditNote.value.trim(),
      idempotency_key: creditKey,
    });
    creditKey = null;
    if (detail.value) detail.value.wallet_balance = res.data.new_balance;
    syncRow({ wallet_balance: res.data.new_balance });
    creditAmount.value = '';
    creditNote.value = '';
    // refresh the ledger quietly (no skeleton flash)
    api.get(`/admin/customers/${selected.value.id}/`).then((r) => { detail.value = r.data; }).catch(() => {});
  } catch (err) {
    creditError.value = err?.response?.data?.detail || t('adminCustomers.creditFailed');
  } finally {
    crediting.value = false;
  }
};

const toggleDriver = async () => {
  togglingDriver.value = true;
  try {
    const res = await api.patch(`/admin/customers/${selected.value.id}/`, { is_driver: !detail.value.is_driver });
    if (detail.value) detail.value.is_driver = res.data.is_driver;
    syncRow({ is_driver: res.data.is_driver });
  } catch {
    /* ignore */
  } finally {
    togglingDriver.value = false;
  }
};

onMounted(fetchCustomers);
</script>
