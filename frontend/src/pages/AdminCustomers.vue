<template>
  <div class="ui-page-shell space-y-5">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t('adminCustomers.kicker') }}</p>
          <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl leading-tight">{{ t('adminCustomers.title') }}</h1>
          <p class="mt-0.5 ui-subtle text-xs hidden sm:block">{{ t('adminCustomers.subtitle') }}</p>
        </div>
        <span v-if="!loading" class="ui-chip shrink-0 tabular-nums">
          {{ t('adminCustomers.totalLabel', { count: total }) }}
        </span>
      </div>
    </header>

    <!-- Search + filters -->
    <div class="ui-toolbar-band">
      <div class="flex flex-wrap items-center gap-3">
        <div class="relative flex-1 min-w-0" style="min-width: 180px">
          <AppIcon name="search" class="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
          <input
            v-model="search"
            type="text"
            class="ui-input ps-10 pe-4 py-2.5 ui-touch-target"
            :aria-label="t('adminCustomers.searchPlaceholder')"
            :placeholder="t('adminCustomers.searchPlaceholder')"
            @input="onSearch"
          />
        </div>
        <label class="flex cursor-pointer items-center gap-2 text-sm text-slate-400 ui-touch-target">
          <input v-model="verifiedOnly" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" @change="reload" />
          {{ t('adminCustomers.filterVerified') }}
        </label>
        <label class="flex cursor-pointer items-center gap-2 text-sm text-slate-400 ui-touch-target">
          <input v-model="driversOnly" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" @change="reload" />
          {{ t('adminCustomers.filterDrivers') }}
        </label>
        <button
          class="ui-btn-outline ui-press ui-touch-target px-4 py-2 text-sm disabled:opacity-50"
          :disabled="loading"
          :aria-busy="loading || undefined"
          @click="reload"
        >
          <span v-if="loading" class="sr-only">{{ t('common.loading') }}</span>
          {{ loading ? '…' : t('adminCustomers.refresh') }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="ui-skeleton overflow-hidden">
      <div v-for="i in 6" :key="i" class="flex items-center gap-4 border-b border-slate-800/60 px-4 py-3">
        <div class="h-3 w-32 animate-pulse rounded bg-slate-700/60" />
        <div class="h-3 w-24 animate-pulse rounded bg-slate-700/40 hidden sm:block" />
        <div class="ms-auto h-3 w-16 animate-pulse rounded bg-slate-800/50" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-red-300">{{ t('adminCustomers.fetchError') }}</p>
      <button class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10 ui-press ui-touch-target" @click="reload">
        {{ t('common.retry') }}
      </button>
    </div>

    <!-- Empty -->
    <div v-else-if="!customers.length" class="ui-empty-state text-center p-8 space-y-1">
      <p class="text-sm font-semibold text-slate-100">{{ t('adminCustomers.empty') }}</p>
      <p class="text-xs text-slate-400">{{ t('adminCustomers.emptyHint') }}</p>
    </div>

    <!-- Data views: table (md+) + card list (mobile) -->
    <template v-else>
      <!-- Desktop table (hidden on mobile) -->
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[640px] text-sm">
          <thead class="bg-slate-800/60 text-xs text-slate-400">
            <tr>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminCustomers.colCustomer') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminCustomers.colContact') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminCustomers.colWallet') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminCustomers.colLoyalty') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminCustomers.colJoined') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
            <tr
              v-for="(c, index) in customers"
              :key="c.id"
              class="ui-reveal cursor-pointer transition-colors hover:bg-slate-800/30"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
              tabindex="0"
              role="button"
              @click="openDetail(c)"
              @keydown.enter="openDetail(c)"
              @keydown.space.prevent="openDetail(c)"
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-slate-200 truncate">{{ c.name || t('adminCustomers.unnamed') }}</span>
                  <span v-if="c.is_driver" class="ui-chip text-[10px] shrink-0 border-emerald-500/40 text-emerald-300">{{ t('adminCustomers.driver') }}</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <div class="flex flex-col gap-0.5">
                  <span class="flex items-center gap-1.5 text-slate-300">
                    {{ c.phone || '—' }}
                    <span v-if="c.phone && c.phone_verified" class="text-[10px] text-emerald-400" aria-hidden="true">✓</span>
                    <span v-if="c.phone && c.phone_verified" class="sr-only">{{ t('adminCustomers.verified') }}</span>
                  </span>
                  <span v-if="c.email" class="text-xs text-slate-500 truncate">{{ c.email }}</span>
                </div>
              </td>
              <td class="px-4 py-3 text-end">
                <span class="font-semibold tabular-nums" :class="parseFloat(c.wallet_balance) > 0 ? 'text-emerald-400' : 'text-slate-500'">
                  {{ fmtMoney(c.wallet_balance) }}
                </span>
              </td>
              <td class="px-4 py-3 text-end tabular-nums text-slate-300">{{ c.loyalty_points }}</td>
              <td class="px-4 py-3 text-end text-xs text-slate-500">{{ fmtDate(c.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mobile card list (hidden on md+) -->
      <ul class="md:hidden space-y-2">
        <li
          v-for="(c, index) in customers"
          :key="c.id"
          class="ui-admin-card ui-reveal ui-surface-lift cursor-pointer"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
          tabindex="0"
          role="button"
          @click="openDetail(c)"
          @keydown.enter="openDetail(c)"
          @keydown.space.prevent="openDetail(c)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-medium text-slate-200 truncate">{{ c.name || t('adminCustomers.unnamed') }}</span>
                <span v-if="c.is_driver" class="ui-chip text-[10px] shrink-0 border-emerald-500/40 text-emerald-300">{{ t('adminCustomers.driver') }}</span>
              </div>
              <p class="mt-0.5 text-xs text-slate-500 truncate">{{ c.phone || c.email || '' }}</p>
            </div>
            <div class="shrink-0 text-end">
              <p class="font-semibold tabular-nums text-sm" :class="parseFloat(c.wallet_balance) > 0 ? 'text-emerald-400' : 'text-slate-500'">{{ fmtMoney(c.wallet_balance) }}</p>
              <p class="text-[10px] text-slate-500 tabular-nums">{{ c.loyalty_points }} pts</p>
            </div>
          </div>
          <p class="mt-1.5 text-[10px] text-slate-600">{{ fmtDate(c.created_at) }}</p>
        </li>
      </ul>
    </template>

    <!-- Pagination -->
    <div v-if="!loading && total > pageSize" class="flex items-center justify-between text-xs text-slate-400">
      <span class="tabular-nums">{{ t('adminCustomers.showing', { from: (page - 1) * pageSize + 1, to: Math.min(page * pageSize, total), total }) }}</span>
      <div class="flex gap-2">
        <button
          class="ui-btn-outline ui-press px-3 py-1.5 text-xs disabled:opacity-40"
          :disabled="page <= 1"
          :aria-label="t('adminCustomers.prev')"
          @click="changePage(page - 1)"
        >
          <AppIcon name="chevron-left" class="h-3.5 w-3.5 rtl:scale-x-[-1]" aria-hidden="true" />
          <span class="ms-1 hidden sm:inline">{{ t('adminCustomers.prev') }}</span>
        </button>
        <button
          class="ui-btn-outline ui-press px-3 py-1.5 text-xs disabled:opacity-40"
          :disabled="page * pageSize >= total"
          :aria-label="t('adminCustomers.next')"
          @click="changePage(page + 1)"
        >
          <span class="me-1 hidden sm:inline">{{ t('adminCustomers.next') }}</span>
          <AppIcon name="chevron-right" class="h-3.5 w-3.5 rtl:scale-x-[-1]" aria-hidden="true" />
        </button>
      </div>
    </div>

    <!-- Customer detail slide-over -->
    <Teleport to="body">
      <Transition enter-active-class="transition-opacity duration-200" enter-from-class="opacity-0" leave-active-class="transition-opacity duration-150" leave-to-class="opacity-0">
        <div v-if="selected" class="fixed inset-0 z-50 bg-black/60" @click.self="selected = null">
          <Transition
            enter-active-class="transition-transform duration-200"
            enter-from-class="ltr:translate-x-full rtl:-translate-x-full"
            leave-active-class="transition-transform duration-150"
            leave-to-class="ltr:translate-x-full rtl:-translate-x-full"
          >
            <!-- TODO: requires logic change — focus trap and focus restore on slide-over open/close (WCAG 2.1.2) -->
            <aside
              v-if="selected"
              class="absolute end-0 top-0 h-full w-full max-w-md overflow-y-auto border-s border-slate-700 bg-slate-900 p-5 space-y-5"
              role="dialog"
              aria-modal="true"
              aria-labelledby="customer-detail-title"
            >
              <!-- Header -->
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="ui-kicker">{{ t('adminCustomers.detailKicker') }}</p>
                  <h2 id="customer-detail-title" class="text-lg font-semibold text-white truncate">{{ selected.name || t('adminCustomers.unnamed') }}</h2>
                  <p class="text-xs text-slate-500 truncate">{{ selected.phone || selected.email || ('#' + selected.id) }}</p>
                </div>
                <button class="ui-press shrink-0 rounded-full p-1.5 text-slate-500 hover:text-slate-300 ui-touch-target" :aria-label="t('common.close')" @click="selected = null">
                  <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
                </button>
              </div>

              <div v-if="loadingDetail" class="space-y-3">
                <div v-for="i in 4" :key="i" class="ui-skeleton h-12" />
              </div>

              <template v-else-if="detail">
                <!-- Summary tiles -->
                <div class="grid grid-cols-2 gap-3">
                  <div class="ui-stat-tile p-3">
                    <p class="ui-stat-label">{{ t('adminCustomers.colWallet') }}</p>
                    <p class="ui-stat-value text-lg tabular-nums text-emerald-400">{{ fmtMoney(detail.wallet_balance) }}</p>
                  </div>
                  <div class="ui-stat-tile p-3">
                    <p class="ui-stat-label">{{ t('adminCustomers.trust') }}</p>
                    <p class="ui-stat-value text-lg tabular-nums">
                      {{ detail.trust.avg_score != null ? detail.trust.avg_score + ' ★' : t('adminCustomers.trustNone') }}
                      <span v-if="detail.trust.count" class="text-xs font-normal text-slate-500">({{ detail.trust.count }})</span>
                    </p>
                  </div>
                </div>
                <div class="flex flex-wrap gap-2">
                  <span
                    class="ui-chip text-[11px]"
                    :class="detail.phone_verified ? 'border-emerald-500/40 text-emerald-300' : ''"
                  >{{ detail.phone_verified ? t('adminCustomers.verified') : t('adminCustomers.unverified') }}</span>
                  <span class="ui-chip text-[11px]">{{ t('adminCustomers.colLoyalty') }}: <span class="tabular-nums">{{ detail.loyalty_points }}</span></span>
                  <span v-if="detail.is_driver" class="ui-chip text-[11px] border-sky-500/40 text-sky-300">{{ t('adminCustomers.driver') }} · <span class="tabular-nums">{{ detail.delivery_jobs }}</span></span>
                </div>

                <!-- Driver toggle -->
                <button
                  class="ui-btn-outline ui-press w-full py-2 text-sm disabled:opacity-50"
                  :class="detail.is_driver ? '' : 'border-sky-500/40 text-sky-300 hover:border-sky-400/70'"
                  :disabled="togglingDriver"
                  @click="toggleDriver"
                >{{ detail.is_driver ? t('adminCustomers.removeDriver') : t('adminCustomers.makeDriver') }}</button>

                <!-- Credit wallet -->
                <div class="ui-admin-card space-y-2.5">
                  <p class="ui-kicker">{{ t('adminCustomers.creditTitle') }}</p>
                  <div class="flex gap-2">
                    <input v-model="creditAmount" type="number" step="0.01" min="0.01" class="ui-input flex-1 text-sm" :placeholder="t('adminCustomers.creditAmount')" :aria-label="t('adminCustomers.creditAmount')" />
                    <button
                      class="ui-btn-primary ui-press shrink-0 px-4 py-2 text-sm disabled:opacity-50"
                      :disabled="crediting || !creditAmount"
                      :aria-busy="crediting || undefined"
                      @click="creditWallet"
                    >
                      <span v-if="crediting" class="sr-only">{{ t('common.loading') }}</span>
                      {{ crediting ? '…' : t('adminCustomers.creditBtn') }}
                    </button>
                  </div>
                  <input v-model="creditNote" type="text" maxlength="200" class="ui-input w-full text-sm" :placeholder="t('adminCustomers.creditNote')" :aria-label="t('adminCustomers.creditNote')" />
                  <p v-if="creditError" class="text-xs text-red-300" role="alert">{{ creditError }}</p>
                </div>

                <!-- Orders across all restaurants -->
                <div class="space-y-2">
                  <p class="ui-kicker">{{ t('adminCustomers.ordersTitle') }}</p>
                  <div v-if="loadingOrders" class="space-y-1.5">
                    <div v-for="i in 3" :key="i" class="ui-skeleton h-9" />
                  </div>
                  <div v-else-if="!orders.length" class="ui-empty-state py-3 text-center">
                    <p class="text-xs text-slate-400">{{ t('adminCustomers.ordersEmpty') }}</p>
                  </div>
                  <ul v-else class="space-y-1.5">
                    <li v-for="o in orders" :key="o.restaurant + o.order_number" class="ui-admin-subcard flex items-center justify-between gap-2 px-3 py-2 text-xs">
                      <div class="min-w-0">
                        <p class="font-medium text-slate-200 truncate">{{ o.restaurant }} <span class="font-mono text-slate-500">#{{ o.order_number }}</span></p>
                        <p class="text-[10px] text-slate-500">{{ orderStatusLabel(o.status) }} · {{ fmtDate(o.created_at) }}</p>
                      </div>
                      <span class="shrink-0 font-semibold tabular-nums text-slate-300">{{ fmtMoney(o.total) }}</span>
                    </li>
                  </ul>
                </div>

                <!-- Cross-restaurant ledger -->
                <div class="space-y-2">
                  <p class="ui-kicker">{{ t('adminCustomers.ledgerTitle') }}</p>
                  <div v-if="!detail.transactions.length" class="ui-empty-state py-3 text-center">
                    <p class="text-xs text-slate-400">{{ t('adminCustomers.ledgerEmpty') }}</p>
                  </div>
                  <ul v-else class="space-y-1.5">
                    <li v-for="tx in detail.transactions" :key="tx.id" class="ui-admin-subcard flex items-center justify-between gap-2 px-3 py-2 text-xs">
                      <div class="min-w-0">
                        <p class="font-medium truncate" :class="isOutflow(tx.type) ? 'text-red-300' : 'text-slate-200'">
                          {{ txLabel(tx.type) }}<span v-if="tx.tenant_name" class="text-slate-500"> · {{ tx.tenant_name }}</span>
                        </p>
                        <p class="text-[10px] text-slate-500">{{ tx.reference || '' }} {{ fmtDate(tx.created_at) }}</p>
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
const orders = ref([]);
const loadingOrders = ref(false);
const ordersScanned = ref(0);

const ORDER_STATUS_KEY = {
  pending: 'orderStatus.statusPending',
  confirmed: 'orderStatus.statusConfirmed',
  preparing: 'orderStatus.statusPreparing',
  ready: 'orderStatus.statusReady',
  completed: 'orderStatus.statusCompleted',
  cancelled: 'orderStatus.statusCancelled',
};
const orderStatusLabel = (s) => t(ORDER_STATUS_KEY[s] || 'orderStatus.statusPending');

const fetchOrders = async (id) => {
  orders.value = [];
  loadingOrders.value = true;
  try {
    const res = await api.get(`/admin/customers/${id}/orders/`);
    orders.value = res.data?.results || [];
    ordersScanned.value = res.data?.scanned_restaurants || 0;
  } catch {
    orders.value = [];
  } finally {
    loadingOrders.value = false;
  }
};

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
  fetchOrders(c.id); // marketplace-wide order history (scans tenant schemas, on-demand)
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
