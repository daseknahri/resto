<template>
  <div class="ui-page-shell space-y-5">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t('adminDeliveryJobs.kicker') }}</p>
          <h1 class="ui-page-title text-xl md:text-2xl leading-tight">{{ t('adminDeliveryJobs.title') }}</h1>
          <p class="mt-0.5 ui-subtle text-xs hidden sm:block">{{ t('adminDeliveryJobs.subtitle') }}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <span v-if="!loading" class="ui-chip tabular-nums">
            {{ countChip }}
          </span>
          <span class="sr-only" aria-live="polite" aria-atomic="true">{{ loading ? t('common.loading') : '' }}</span>
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1.5 px-4 py-2 text-sm disabled:opacity-50"
            :disabled="loading || refreshing"
            :aria-busy="loading || refreshing"
            @click="fetchJobs({ background: true })"
          >
            <svg v-if="loading || refreshing" aria-hidden="true" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" class="h-4 w-4 animate-spin shrink-0"><path d="M3 8a5 5 0 1 0 1.2-3.2M3 5v3h3"/></svg>
            {{ (loading || refreshing) ? t('common.loading') : t('adminDeliveryJobs.refresh') }}
          </button>
        </div>
      </div>
    </header>

    <!-- Status filter chips -->
    <div class="ui-scroll-row min-w-0" role="radiogroup" :aria-label="t('adminDeliveryJobs.filterLabel')">
      <button
        v-for="s in STATUSES"
        :key="s"
        role="radio"
        class="ui-state-chip shrink-0 ui-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70"
        :data-active="statusFilter === s ? 'true' : 'false'"
        :aria-checked="statusFilter === s"
        @click="setFilter(s)"
      >{{ s === 'all' ? t('adminDeliveryJobs.all') : statusLabel(s) }}</button>
    </div>

    <!-- Tenant filter + search (A2-18): the list endpoint already supports ?tenant_id= -->
    <div class="flex flex-wrap items-center gap-2">
      <label class="sr-only" for="jobs-tenant-filter">{{ t('adminDeliveryJobs.tenantFilterLabel') }}</label>
      <select
        id="jobs-tenant-filter"
        class="shrink-0 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-200"
        :value="tenantFilter"
        @change="setTenantFilter($event.target.value)"
      >
        <option value="all">{{ t('adminDeliveryJobs.tenantAll') }}</option>
        <option v-for="tn in tenants" :key="tn.id" :value="String(tn.id)">{{ tn.name }}</option>
      </select>
      <label class="sr-only" for="jobs-search">{{ t('adminDeliveryJobs.searchLabel') }}</label>
      <input
        id="jobs-search"
        v-model="searchText"
        type="search"
        class="min-w-[180px] flex-1 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-slate-200"
        :placeholder="t('adminDeliveryJobs.searchPlaceholder')"
      />
    </div>

    <!-- Job action failed (A2-19): the rows stay, the row buttons retry -->
    <div v-if="actionError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-red-300">{{ t('adminDeliveryJobs.actionFailed') }}</p>
    </div>

    <!-- Background poll failed: keep the last loaded rows, surface a retry (A2-06) -->
    <div v-if="refreshFailed && !loading" class="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-amber-300">{{ t('adminDeliveryJobs.refreshFailed') }}</p>
      <button
        class="shrink-0 rounded-lg border border-amber-500/40 px-3 py-1 text-xs font-semibold text-amber-300 hover:bg-amber-500/10 ui-press"
        @click="fetchJobs({ background: true })"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="ui-skeleton overflow-hidden">
      <div v-for="i in 6" :key="i" class="flex items-center gap-4 border-b border-slate-800/60 px-4 py-3">
        <div class="h-3 w-24 animate-pulse rounded bg-slate-700/60" />
        <div class="h-3 w-32 animate-pulse rounded bg-slate-700/40 hidden sm:block" />
        <div class="ms-auto h-3 w-16 animate-pulse rounded bg-slate-800/50" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-red-300">{{ t('adminDeliveryJobs.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 hover:bg-red-500/10 ui-press"
        @click="fetchJobs"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="!displayedJobs.length" class="ui-empty-state text-center p-8 space-y-1">
      <p class="text-sm font-semibold text-slate-100">{{ searchText ? t('adminDeliveryJobs.emptySearch') : t('adminDeliveryJobs.empty') }}</p>
      <p v-if="!searchText" class="text-xs text-slate-400">{{ t('adminDeliveryJobs.emptyHint') }}</p>
    </div>

    <!-- Data views: table (md+) + card list (mobile) -->
    <template v-else>
      <!-- Desktop table (hidden on mobile) -->
      <div class="ui-table-wrap hidden md:block">
        <table class="w-full min-w-[680px] text-sm">
          <thead class="bg-slate-800/60 text-xs text-slate-400">
            <tr>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDeliveryJobs.colOrder') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDeliveryJobs.colRestaurant') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDeliveryJobs.colDriver') }}</th>
              <th scope="col" class="px-4 py-3 text-start">{{ t('adminDeliveryJobs.colStatus') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDeliveryJobs.colPayout') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDeliveryJobs.colCreated') }}</th>
              <th scope="col" class="px-4 py-3 text-end">{{ t('adminDeliveryJobs.colDetails') }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-700/40">
            <template v-for="(j, index) in displayedJobs" :key="j.id">
            <tr
              class="ui-reveal transition-colors hover:bg-slate-800/30"
              :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
            >
              <td class="px-4 py-3 font-mono text-xs text-slate-300">#{{ j.order_number }}</td>
              <td class="px-4 py-3 text-slate-200 max-w-[160px] truncate" :title="j.tenant_name || ('#' + j.tenant_id)">{{ j.tenant_name || ('#' + j.tenant_id) }}</td>
              <td class="px-4 py-3 text-slate-400">
                <span v-if="j.driver" class="truncate">{{ j.driver.name || j.driver.phone || ('#' + j.driver.id) }}</span>
                <span v-else class="italic text-slate-600">{{ t('adminDeliveryJobs.unassigned') }}</span>
              </td>
              <td class="px-4 py-3">
                <span class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold" :class="statusClass(j.status)" :aria-label="t('adminDeliveryJobs.colStatus') + ': ' + statusLabel(j.status, j.business_type)">{{ statusLabel(j.status, j.business_type) }}</span>
                <p v-if="j.status === 'failed' && j.failure_reason" class="mt-1 max-w-[220px] text-[11px] leading-snug text-red-300">{{ t('adminDeliveryJobs.failureReason', { reason: failureLabel(j.failure_reason) }) }}</p>
                <p v-if="j.status === 'failed' && j.failure_note" class="mt-0.5 max-w-[220px] text-[11px] leading-snug text-slate-400">{{ t('adminDeliveryJobs.failureNote', { note: j.failure_note }) }}</p>
                <p v-if="j.resolution" class="mt-0.5 max-w-[220px] text-[11px] leading-snug text-slate-400">{{ t('adminDeliveryJobs.resolutionLine', { resolution: resolutionLabel(j.resolution) }) }}</p>
              </td>
              <td class="px-4 py-3 text-end tabular-nums" :class="j.status === 'delivered' ? 'text-emerald-300' : 'text-slate-400'">{{ fmtMoney(j.driver_payout) }}<span v-if="j.status !== 'delivered'" class="block text-[10px] font-normal text-slate-500">{{ t('adminDeliveryJobs.payoutIfDelivered') }}</span></td>
              <td class="px-4 py-3 text-end text-xs text-slate-500 tabular-nums">{{ fmtDate(j.created_at) }}</td>
              <td class="px-4 py-3 text-end">
                <button
                  class="rounded-lg border border-slate-700 px-2.5 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press"
                  @click="toggleDetails(j.id)"
                  :aria-expanded="expandedJobId === j.id"
                >{{ expandedJobId === j.id ? t('adminDeliveryJobs.hideDetails') : t('adminDeliveryJobs.details') }}</button>
              </td>
            </tr>
            <tr v-if="expandedJobId === j.id" class="bg-slate-800/30">
              <td colspan="7" class="px-4 py-3">
                <div class="grid gap-x-6 gap-y-1 sm:grid-cols-2 text-xs">
                  <p><span class="text-slate-500">{{ t('adminDeliveryJobs.detailDriver') }}: </span><span class="text-slate-200">{{ j.driver ? (j.driver.name || j.driver.phone || ('#' + j.driver.id)) : t('adminDeliveryJobs.unassigned') }}</span><span v-if="j.driver && j.driver.name && j.driver.phone" class="text-slate-400"> · {{ j.driver.phone }}</span><span v-if="j.driver && j.driver.vehicle" class="text-slate-400"> · {{ j.driver.vehicle }}</span></p>
                  <p><span class="text-slate-500">{{ t('adminDeliveryJobs.detailDistance') }}: </span><span class="text-slate-200 tabular-nums">{{ j.distance_km != null ? j.distance_km + ' km' : '—' }}</span></p>
                  <p><span class="text-slate-500">{{ t('adminDeliveryJobs.detailPickup') }}: </span><span class="text-slate-200">{{ j.pickup_address || '—' }}</span></p>
                  <p><span class="text-slate-500">{{ t('adminDeliveryJobs.detailDelivery') }}: </span><span class="text-slate-200">{{ j.delivery_address || '—' }}</span></p>
                  <p><span class="text-slate-500">{{ t('adminDeliveryJobs.detailFee') }}: </span><span class="text-slate-200 tabular-nums">{{ fmtMoney(j.delivery_fee) }}</span></p>
                  <p><span class="text-slate-500">{{ t('adminDeliveryJobs.detailCommission') }}: </span><span class="text-slate-200 tabular-nums">{{ fmtMoney(j.platform_commission) }}</span></p>
                </div>
                <p class="mt-2 text-xs text-slate-500">{{ t('adminDeliveryJobs.detailTimeline') }}: <span class="text-slate-300">{{ timelineText(j) }}</span></p>
                <div class="mt-2 flex flex-wrap gap-2">
                  <button
                    v-if="j.status === 'failed'"
                    class="rounded-lg border border-amber-500/40 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/10 ui-press disabled:opacity-40"
                    :disabled="actingJobId === j.id"
                    @click="doJobAction(j, 'redispatch')"
                  >{{ t('adminDeliveryJobs.redispatch') }}</button>
                  <button
                    v-if="!isTerminal(j.status)"
                    class="rounded-lg border border-red-500/40 px-3 py-1.5 text-xs font-semibold text-red-300 hover:bg-red-500/10 ui-press disabled:opacity-40"
                    :disabled="actingJobId === j.id"
                    @click="doJobAction(j, 'cancel')"
                  >{{ t('adminDeliveryJobs.cancelJob') }}</button>
                </div>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Mobile card list (hidden on md+) -->
      <ul class="md:hidden space-y-2">
        <li
          v-for="(j, index) in displayedJobs"
          :key="j.id"
          class="ui-admin-card ui-reveal"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-mono text-xs text-slate-400">#{{ j.order_number }}</span>
                <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold" :class="statusClass(j.status)" :aria-label="t('adminDeliveryJobs.colStatus') + ': ' + statusLabel(j.status, j.business_type)">{{ statusLabel(j.status, j.business_type) }}</span>
              </div>
              <p class="mt-0.5 text-sm font-medium text-slate-200 truncate">{{ j.tenant_name || ('#' + j.tenant_id) }}</p>
              <p class="mt-0.5 text-xs text-slate-500 truncate">
                <span v-if="j.driver">{{ j.driver.name || j.driver.phone || ('#' + j.driver.id) }}</span>
                <span v-else class="italic text-slate-600">{{ t('adminDeliveryJobs.unassigned') }}</span>
              </p>
            </div>
            <div class="shrink-0 text-end">
              <p class="font-semibold tabular-nums text-sm" :class="j.status === 'delivered' ? 'text-emerald-300' : 'text-slate-400'">{{ fmtMoney(j.driver_payout) }}<span v-if="j.status !== 'delivered'" class="block text-[10px] font-normal text-slate-500">{{ t('adminDeliveryJobs.payoutIfDelivered') }}</span></p>
              <p class="mt-0.5 text-[10px] text-slate-600 tabular-nums">{{ fmtDate(j.created_at) }}</p>
            </div>
          </div>
          <p v-if="j.status === 'failed' && j.failure_reason" class="mt-1.5 text-[11px] leading-snug text-red-300">{{ t('adminDeliveryJobs.failureReason', { reason: failureLabel(j.failure_reason) }) }}</p>
          <p v-if="j.status === 'failed' && j.failure_note" class="mt-0.5 text-[11px] leading-snug text-slate-400">{{ t('adminDeliveryJobs.failureNote', { note: j.failure_note }) }}</p>
          <p v-if="j.resolution" class="mt-0.5 text-[11px] leading-snug text-slate-400">{{ t('adminDeliveryJobs.resolutionLine', { resolution: resolutionLabel(j.resolution) }) }}</p>
          <div class="mt-2 flex items-center gap-2">
            <button
              class="rounded-lg border border-slate-700 px-2.5 py-1 text-[11px] font-semibold text-slate-300 hover:bg-slate-800 ui-press"
              @click="toggleDetails(j.id)"
              :aria-expanded="expandedJobId === j.id"
            >{{ expandedJobId === j.id ? t('adminDeliveryJobs.hideDetails') : t('adminDeliveryJobs.details') }}</button>
          </div>
          <div v-if="expandedJobId === j.id" class="mt-2 space-y-1 border-t border-slate-700/40 pt-2 text-xs">
            <p><span class="text-slate-500">{{ t('adminDeliveryJobs.detailPickup') }}: </span><span class="text-slate-200">{{ j.pickup_address || '—' }}</span></p>
            <p><span class="text-slate-500">{{ t('adminDeliveryJobs.detailDelivery') }}: </span><span class="text-slate-200">{{ j.delivery_address || '—' }}</span></p>
            <p class="text-slate-500">{{ t('adminDeliveryJobs.detailTimeline') }}: <span class="text-slate-300">{{ timelineText(j) }}</span></p>
            <div class="flex flex-wrap gap-2 pt-1">
              <button
                v-if="j.status === 'failed'"
                class="rounded-lg border border-amber-500/40 px-3 py-1.5 text-xs font-semibold text-amber-300 hover:bg-amber-500/10 ui-press disabled:opacity-40"
                :disabled="actingJobId === j.id"
                @click="doJobAction(j, 'redispatch')"
              >{{ t('adminDeliveryJobs.redispatch') }}</button>
              <button
                v-if="!isTerminal(j.status)"
                class="rounded-lg border border-red-500/40 px-3 py-1.5 text-xs font-semibold text-red-300 hover:bg-red-500/10 ui-press disabled:opacity-40"
                :disabled="actingJobId === j.id"
                @click="doJobAction(j, 'cancel')"
              >{{ t('adminDeliveryJobs.cancelJob') }}</button>
            </div>
          </div>
        </li>
      </ul>

      <!-- Cap + pagination (A2-07): the server total, not jobs.length -->
      <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p class="text-xs text-slate-500">{{ t('adminDeliveryJobs.showingLatest', { count: displayedJobs.length, total }) }}</p>
        <div v-if="totalPages > 1" class="flex items-center gap-2">
          <button
            class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press disabled:opacity-40"
            :disabled="page <= 1"
            @click="prevPage"
          >{{ t('adminDeliveryJobs.prevPage') }}</button>
          <span class="text-xs text-slate-400 tabular-nums">{{ t('adminDeliveryJobs.pageOf', { page, pages: totalPages }) }}</span>
          <button
            class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-800 ui-press disabled:opacity-40"
            :disabled="page >= totalPages"
            @click="nextPage"
          >{{ t('adminDeliveryJobs.nextPage') }}</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import { formatCurrencyString } from '../lib/intlFormatters';
import AppIcon from '../components/AppIcon.vue';
import { pickupLabelKey } from '../lib/deliveryVocab';
import { useConfirmModal } from '../composables/useConfirmModal';

const { t, currentLocale } = useI18n();
const { confirm } = useConfirmModal();

const STATUSES = ['all', 'searching', 'assigned', 'at_restaurant', 'picked_up', 'delivered', 'failed', 'cancelled'];
const PAGE_SIZE = 100;
const loading = ref(true);
const refreshing = ref(false);
const fetchError = ref(false);
const refreshFailed = ref(false);
const jobs = ref([]);
const total = ref(0);
const page = ref(1);
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));
const statusFilter = ref('all');
const tenants = ref([]);
const tenantFilter = ref('all');
const searchText = ref('');
const expandedJobId = ref(null);
const actingJobId = ref(null);
const actionError = ref(false);

// A2-20: the chip is the SERVER total for the active server-side filters
// (status + tenant), labelled with the filter — never the raw row count.
const activeFilterLabel = computed(() => {
  const parts = [];
  if (statusFilter.value !== 'all') parts.push(statusLabel(statusFilter.value));
  if (tenantFilter.value !== 'all') {
    const tn = tenants.value.find((x) => String(x.id) === tenantFilter.value);
    parts.push(tn ? tn.name : ('#' + tenantFilter.value));
  }
  return parts.join(' · ');
});
const countChip = computed(() => {
  const f = activeFilterLabel.value;
  return f
    ? t('adminDeliveryJobs.filteredTotalLabel', { count: total.value, filter: f })
    : t('adminDeliveryJobs.totalLabel', { count: total.value });
});

// A2-18: client-side search over the loaded page (order / restaurant / driver).
const displayedJobs = computed(() => {
  const q = searchText.value.trim().toLowerCase();
  if (!q) return jobs.value;
  return jobs.value.filter((j) => {
    const hay = [j.order_number, j.tenant_name, j.driver?.name, j.driver?.phone]
      .filter(Boolean).join(' ').toLowerCase();
    return hay.includes(q);
  });
});

const STATUS_LABELS = {
  searching: 'adminDeliveryJobs.statusSearching',
  assigned: 'adminDeliveryJobs.statusAssigned',
  at_restaurant: 'adminDeliveryJobs.statusAtRestaurant',
  picked_up: 'adminDeliveryJobs.statusPickedUp',
  delivered: 'adminDeliveryJobs.statusDelivered',
  failed: 'adminDeliveryJobs.statusFailed',
  cancelled: 'adminDeliveryJobs.statusCancelled',
};
// For at_restaurant chips, branch on the job's business_type; all others use static map.
const statusLabel = (s, businessType) => {
  if (s === 'at_restaurant') return t(pickupLabelKey(businessType, 'at'));
  return t(STATUS_LABELS[s] || 'adminDeliveryJobs.statusUnknown');
};

const FAILURE_REASON_LABELS = {
  customer_no_show: 'adminDeliveryJobs.failureCustomerNoShow',
  bad_address: 'adminDeliveryJobs.failureBadAddress',
  driver_unable: 'adminDeliveryJobs.failureDriverUnable',
  other: 'adminDeliveryJobs.failureOther',
};
const failureLabel = (r) => t(FAILURE_REASON_LABELS[r] || 'adminDeliveryJobs.statusUnknown');

const RESOLUTION_LABELS = {
  redispatched: 'adminDeliveryJobs.resolutionRedispatched',
  refunded_cancelled: 'adminDeliveryJobs.resolutionRefundedCancelled',
  noshow_paid: 'adminDeliveryJobs.resolutionNoshowPaid',
};
const resolutionLabel = (r) => t(RESOLUTION_LABELS[r] || 'adminDeliveryJobs.statusUnknown');

const isTerminal = (st) => st === 'delivered' || st === 'failed' || st === 'cancelled';

// A2-18 detail: one line — created + every timestamp the job actually has.
const timelineText = (j) => {
  const parts = [`${t('adminDeliveryJobs.colCreated')}: ${fmtDate(j.created_at) || '—'}`];
  if (j.assigned_at) parts.push(`${t('adminDeliveryJobs.statusAssigned')}: ${fmtDate(j.assigned_at)}`);
  if (j.picked_up_at) parts.push(`${t('adminDeliveryJobs.statusPickedUp')}: ${fmtDate(j.picked_up_at)}`);
  if (j.delivered_at) parts.push(`${t('adminDeliveryJobs.statusDelivered')}: ${fmtDate(j.delivered_at)}`);
  if (j.failed_at) parts.push(`${t('adminDeliveryJobs.statusFailed')}: ${fmtDate(j.failed_at)}`);
  return parts.join(' · ');
};

const statusClass = (s) => {
  if (s === 'delivered') return 'bg-emerald-500/12 text-emerald-300';
  if (s === 'failed') return 'bg-red-500/12 text-red-300';
  if (s === 'cancelled') return 'bg-slate-500/15 text-slate-300';
  if (s === 'searching') return 'bg-amber-500/12 text-amber-300';
  return 'bg-sky-500/12 text-sky-300';
};

const fmtMoney = (v) =>
  formatCurrencyString(currentLocale.value, v, 'MAD', { maximumFractionDigits: 2 });

const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Intl.DateTimeFormat(currentLocale.value, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  } catch {
    return iso.slice(0, 16);
  }
};

const fetchJobs = async ({ background = false } = {}) => {
  // A2-06: background polls (20s timer, tab-visible) must not flash the skeleton
  // board — they only flip `refreshing`, and a failed poll keeps the last loaded
  // rows with a retry banner instead of swapping in the full error panel.
  if (background) refreshing.value = true;
  else loading.value = true;
  fetchError.value = false;
  try {
    const params = { page: page.value, page_size: PAGE_SIZE };
    if (statusFilter.value !== 'all') params.status = statusFilter.value;
    if (tenantFilter.value !== 'all') params.tenant_id = tenantFilter.value;
    const res = await api.get('/admin/delivery-jobs/', { params });
    jobs.value = Array.isArray(res.data) ? res.data : (res.data?.results || []);
    // A2-07: the envelope total is the count chip + cap note; a bare array has no
    // total, so fall back to the rows actually returned.
    total.value = typeof res.data?.total === 'number' ? res.data.total : jobs.value.length;
    // A2-18: drop a detail panel whose job left the page (filter/page change).
    if (expandedJobId.value !== null && !jobs.value.some((x) => x.id === expandedJobId.value)) expandedJobId.value = null;
    refreshFailed.value = false;
  } catch {
    if (background) refreshFailed.value = true;
    else fetchError.value = true;
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
};

const setFilter = (s) => {
  statusFilter.value = s;
  page.value = 1;
  fetchJobs();
};

const prevPage = () => {
  if (page.value <= 1) return;
  page.value -= 1;
  fetchJobs();
};

const nextPage = () => {
  if (page.value >= totalPages.value) return;
  page.value += 1;
  fetchJobs();
};

// A2-18: tenant options for the filter (same envelope as AdminConsole reads).
const fetchTenants = async () => {
  try {
    const res = await api.get('/admin-tenants/', { params: { page: 1, page_size: 200 } });
    const payload = res?.data;
    tenants.value = Array.isArray(payload) ? payload : (Array.isArray(payload?.results) ? payload.results : []);
  } catch {
    tenants.value = [];
  }
};

const setTenantFilter = (v) => {
  tenantFilter.value = v;
  page.value = 1;
  fetchJobs();
};

const toggleDetails = (id) => {
  expandedJobId.value = expandedJobId.value === id ? null : id;
};

// A2-19: board actions — POST /admin/delivery-jobs/<id>/action/ (confirm first,
// house style via useConfirmModal). The row updates in place from the returned
// job; tenant_name is list-enriched, not serialized, so it is preserved.
const doJobAction = async (j, action) => {
  const ok = await confirm({
    title: action === 'redispatch'
      ? t('adminDeliveryJobs.redispatchConfirmTitle')
      : t('adminDeliveryJobs.cancelConfirmTitle'),
    body: action === 'redispatch'
      ? t('adminDeliveryJobs.redispatchConfirmBody', { order: j.order_number })
      : t('adminDeliveryJobs.cancelConfirmBody', { order: j.order_number }),
    confirmLabel: action === 'redispatch'
      ? t('adminDeliveryJobs.redispatch')
      : t('adminDeliveryJobs.cancelJob'),
    danger: action === 'cancel',
  });
  if (!ok) return;
  actingJobId.value = j.id;
  actionError.value = false;
  try {
    const res = await api.post(`/admin/delivery-jobs/${j.id}/action/`, { action });
    const updated = res?.data?.job;
    if (updated) {
      jobs.value = jobs.value.map((x) => (x.id === j.id
        ? { ...updated, tenant_name: x.tenant_name }
        : x));
    } else {
      fetchJobs({ background: true });
    }
  } catch {
    actionError.value = true;
  } finally {
    actingJobId.value = null;
  }
};

// ── Live-ish polling: an ops board left open must not go stale for a whole shift ──
const POLL_MS = 20000;
let pollTimer = null;

const onVisibilityChange = () => {
  if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
    fetchJobs({ background: true });
  }
};

onMounted(() => {
  fetchJobs();
  fetchTenants();
  pollTimer = setInterval(() => fetchJobs({ background: true }), POLL_MS);
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange);
  }
});

onUnmounted(() => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', onVisibilityChange);
  }
});
</script>
