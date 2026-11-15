<template>
  <div class="ui-page-shell space-y-6">
    <!-- Header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="ui-kicker">{{ t('adminAnalytics.kicker') }}</p>
          <h1 class="ui-display text-xl font-semibold tracking-tight text-white md:text-2xl leading-tight">
            {{ t('adminAnalytics.title') }}
          </h1>
          <p class="ui-subtle mt-0.5 text-xs">{{ t('adminAnalytics.subtitle') }}</p>
        </div>
        <!-- Silent refresh indicator (shown when data is already visible but re-fetching) -->
        <span
          v-if="loading && data"
          class="text-[11px] text-slate-500 tabular-nums"
          role="status"
          aria-live="polite"
        >{{ t('adminAnalytics.updating') }}</span>
        <button
          class="ui-btn-outline ui-press ui-touch-target shrink-0 flex items-center gap-2 px-4 text-xs disabled:opacity-50"
          :disabled="loading"
          @click="refresh"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 20 20"
            fill="currentColor"
            class="h-4 w-4 shrink-0"
            :class="loading ? 'animate-spin motion-reduce:animate-none' : ''"
          >
            <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" />
          </svg>
          <span>{{ t('adminAnalytics.refresh') }}</span>
        </button>
      </div>
    </header>

    <!-- Period selector (A-15): presets scope the flow figures; "All time" is the historic default -->
    <div class="flex flex-wrap items-center gap-2" role="group" :aria-label="t('adminAnalytics.periodLabel')">
      <span class="text-xs text-slate-400">{{ t('adminAnalytics.periodLabel') }}</span>
      <button
        v-for="p in periods"
        :key="p.value"
        type="button"
        class="ui-btn-outline ui-press px-3 py-1 text-xs"
        :class="period === p.value ? 'border-white/40 bg-white/10 text-white' : ''"
        :aria-pressed="period === p.value ? 'true' : 'false'"
        :disabled="loading"
        @click="setPeriod(p.value)"
      >{{ t(p.labelKey) }}</button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !data" aria-busy="true" :aria-label="t('common.loading')" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
      <div v-for="i in 12" :key="i" class="ui-skeleton h-24" />
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('adminAnalytics.fetchError') }}</p>
      <button
        class="ui-press shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 ui-touch-target"
        @click="refresh"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Data -->
    <template v-else-if="data">
      <p class="sr-only" aria-live="polite" aria-atomic="true">{{ t('adminAnalytics.loaded') }}</p>
      <!-- Money model: outstanding liabilities -->
      <section v-if="data.financials" class="ui-reveal space-y-3">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionFinancials') }}</h2>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard :value="currency(data.financials.customer_wallet_liability)" :label="t('adminAnalytics.walletLiability')" color="violet" icon="wallet" :to="{ name: 'admin-wallets' }" />
          <StatCard :value="currency(data.financials.restaurant_float_outstanding)" :label="t('adminAnalytics.floatOutstanding')" color="sky" icon="receipt" :to="{ name: 'admin-console' }" />
          <StatCard :value="currency(data.financials.driver_owed)" :label="t('adminAnalytics.driverOwed')" color="emerald" icon="truck" :to="{ name: 'admin-wallets' }" />
        </div>
        <p class="text-[11px] text-slate-500">{{ t('adminAnalytics.financialsHint') }}</p>
      </section>

      <!-- Restaurants -->
      <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '28ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionTenants') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard :value="data.tenants.total" :label="t('adminAnalytics.totalTenants')" color="sky" icon="location" :to="{ name: 'admin-console' }" />
          <StatCard :value="data.tenants.active" :label="t('adminAnalytics.activeTenants')" color="emerald" icon="location" :to="{ name: 'admin-console' }" />
          <StatCard :value="data.tenants.suspended" :label="t('adminAnalytics.suspendedTenants')" color="amber" icon="location" :to="{ name: 'admin-console' }" />
          <StatCard :value="data.tenants.canceled" :label="t('adminAnalytics.canceledTenants')" color="red" icon="close" :to="{ name: 'admin-console' }" />
        </div>
      </section>

      <!-- Customers & Drivers -->
      <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '56ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionCustomers') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <StatCard :value="data.customers.total" :label="t('adminAnalytics.totalCustomers')" color="violet" icon="users" :to="{ name: 'admin-customers' }" />
          <StatCard :value="data.customers.drivers_total" :label="t('adminAnalytics.totalDrivers')" color="sky" icon="user" :to="{ name: 'admin-drivers' }" />
          <StatCard :value="data.customers.drivers_online" :label="t('adminAnalytics.driversOnline')" color="emerald" icon="user" :to="{ name: 'admin-drivers' }" />
        </div>
      </section>

      <!-- Deliveries -->
      <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '84ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionDeliveries') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          <StatCard :value="data.deliveries.total_jobs" :label="t('adminAnalytics.totalJobs')" color="sky" icon="receipt" :to="{ name: 'admin-delivery-jobs' }" />
          <StatCard :value="data.deliveries.delivered" :label="t('adminAnalytics.deliveredJobs')" color="emerald" icon="truck" :to="{ name: 'admin-delivery-jobs' }" />
          <StatCard :value="data.deliveries.active" :label="t('adminAnalytics.activeJobs')" color="amber" icon="refresh" :to="{ name: 'admin-delivery-jobs' }" />
          <StatCard :value="data.deliveries.searching" :label="t('adminAnalytics.searchingJobs')" color="sky" icon="search" :to="{ name: 'admin-delivery-jobs' }" />
          <StatCard :value="data.deliveries.failed" :label="t('adminAnalytics.failedJobs')" color="red" icon="close" :to="{ name: 'admin-delivery-jobs' }" />
          <StatCard
            :value="data.deliveries.avg_driver_rating != null ? formatRating(data.deliveries.avg_driver_rating) : '—'"
            :label="t('adminAnalytics.avgDriverRating')"
            color="amber"
            icon="sparkles" :to="{ name: 'admin-drivers' }"
          />
          <StatCard
            :value="data.deliveries.total_fees != null ? currency(data.deliveries.total_fees) : '—'"
            :label="t('adminAnalytics.totalFees')"
            color="sky"
            icon="receipt" :to="{ name: 'admin-delivery-jobs' }"
          />
          <StatCard
            :value="data.deliveries.total_driver_payouts != null ? currency(data.deliveries.total_driver_payouts) : '—'"
            :label="t('adminAnalytics.totalPayouts')"
            color="violet"
            icon="wallet" :to="{ name: 'admin-delivery-jobs' }"
          />
        </div>
      </section>

      <!-- Rides -->
      <section v-if="data.rides" class="ui-reveal space-y-3" :style="{ '--ui-delay': '98ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.ridesTitle') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard :value="data.rides.total" :label="t('adminAnalytics.ridesTotal')" color="sky" icon="truck" :to="{ name: 'admin-rides' }" />
          <StatCard :value="data.rides.completed" :label="t('adminAnalytics.ridesCompleted')" color="emerald" icon="truck" :to="{ name: 'admin-rides' }" />
          <StatCard :value="data.rides.active" :label="t('adminAnalytics.ridesActive')" color="amber" icon="refresh" :to="{ name: 'admin-rides' }" />
          <StatCard :value="data.rides.cancelled" :label="t('adminAnalytics.ridesCancelled')" color="red" icon="close" :to="{ name: 'admin-rides' }" />
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatCard
            :value="data.rides.fare_gmv != null ? currency(data.rides.fare_gmv) : '—'"
            :label="t('adminAnalytics.ridesGmv')"
            color="violet"
            icon="wallet" :to="{ name: 'admin-rides' }"
          />
          <div class="ui-card px-4 py-3 flex flex-col justify-center space-y-0.5">
            <p class="ui-stat-label">{{ t('adminAnalytics.ridesPayment') }}</p>
            <p class="text-sm font-semibold tabular-nums text-slate-200">
              {{ t('adminAnalytics.ridesWalletCash', { wallet: data.rides.wallet_paid, cash: data.rides.cash_paid }) }}
            </p>
          </div>
        </div>
      </section>

      <!-- Zones & Flash Sales side by side -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Zones -->
        <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '112ms' }">
          <h2 class="ui-kicker">{{ t('adminAnalytics.sectionZones') }}</h2>
          <div class="grid grid-cols-2 gap-4">
            <StatCard :value="data.zones.total" :label="t('adminAnalytics.totalZones')" color="sky" icon="location" :to="{ name: 'admin-delivery-zones' }" />
            <StatCard :value="data.zones.active" :label="t('adminAnalytics.activeZones')" color="emerald" icon="location" :to="{ name: 'admin-delivery-zones' }" />
          </div>
        </section>

        <!-- Flash Sales -->
        <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '112ms' }">
          <h2 class="ui-kicker">{{ t('adminAnalytics.sectionFlashSales') }}</h2>
          <div class="grid grid-cols-3 gap-4">
            <StatCard :value="data.flash_sales.total" :label="t('adminAnalytics.totalSales')" color="sky" icon="sparkles" :to="{ name: 'admin-flash-sales' }" />
            <StatCard :value="data.flash_sales.live" :label="t('adminAnalytics.liveSales')" color="emerald" icon="sparkles" :to="{ name: 'admin-flash-sales' }" />
            <StatCard :value="data.flash_sales.total_redemptions" :label="t('adminAnalytics.redemptions')" color="amber" icon="receipt" :to="{ name: 'admin-flash-sales' }" />
          </div>
        </section>
      </div>

      <!-- Revenue by vertical -->
      <section v-if="data.revenue_by_vertical" class="ui-reveal space-y-3" :style="{ '--ui-delay': '126ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionRevenueByVertical') }}</h2>
        <div class="ui-card overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-start text-[11px] uppercase tracking-wide text-slate-500">
                <th scope="col" class="px-4 py-2 text-start font-medium">{{ t('adminAnalytics.revenueVerticalCol') }}</th>
                <th scope="col" class="px-4 py-2 text-end font-medium">{{ t('adminAnalytics.revenueTotalCol') }}</th>
                <th scope="col" class="px-4 py-2 text-end font-medium">{{ t('adminAnalytics.revenueTxnsCol') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.revenue_by_vertical" :key="row.vertical" class="border-t border-white/5">
                <td class="px-4 py-2 text-slate-200">{{ t(`adminAnalytics.vertical_${row.vertical}`) }}</td>
                <td class="px-4 py-2 text-end tabular-nums text-slate-200">{{ currency(row.total) }}</td>
                <td class="px-4 py-2 text-end tabular-nums text-slate-500">{{ row.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-[11px] text-slate-500">{{ t('adminAnalytics.revenueByVerticalHint') }}</p>
      </section>

      <!-- Wallet -->
      <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '140ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionWallet') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard
            :value="data.wallet.total_balance != null ? currency(data.wallet.total_balance) : '—'"
            :label="t('adminAnalytics.totalBalance')"
            color="emerald"
            icon="wallet" :to="{ name: 'admin-wallets' }"
          />
          <StatCard :value="data.wallet.total_transactions" :label="t('adminAnalytics.totalTxns')" color="sky" icon="receipt" :to="{ name: 'admin-wallets' }" />
          <StatCard
            :value="data.wallet.total_bonus_issued != null ? currency(data.wallet.total_bonus_issued) : '—'"
            :label="t('adminAnalytics.bonusIssued')"
            color="amber"
            icon="sparkles" :to="{ name: 'admin-wallets' }"
          />
          <StatCard
            :value="data.wallet.total_payments != null ? currency(data.wallet.total_payments) : '—'"
            :label="t('adminAnalytics.payments')"
            color="violet"
            icon="wallet" :to="{ name: 'admin-wallets' }"
          />
        </div>
      </section>

      <!-- Last refreshed -->
      <p class="text-[11px] text-slate-500 text-end tabular-nums">{{ t('adminAnalytics.lastRefreshed') }} {{ refreshedAt }}</p>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';

const { t, currentLocale } = useI18n();

const loading = ref(false);
const fetchError = ref(false);
const data = ref(null);
const refreshedAt = ref('');
// A-15: period presets; "all" is the historic all-time default.
const period = ref('all');
const periods = [
  { value: 'all', labelKey: 'adminAnalytics.periodAll' },
  { value: '7d', labelKey: 'adminAnalytics.period7d' },
  { value: '30d', labelKey: 'adminAnalytics.period30d' },
];

const setPeriod = (p) => {
  if (period.value === p || loading.value) return;
  period.value = p;
  refresh();
};

// A-18: 1 decimal (the backend already rounds via _f(..., 1)); the star is the
// card's AppIcon now, not a hardcoded character in the value.
const formatRating = (val) => {
  const n = Number(val);
  return Number.isFinite(n) ? n.toFixed(1) : '—';
};

const currency = (val) => {
  if (val == null) return '—';
  return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'MAD', minimumFractionDigits: 2 }).format(val);
};

const refresh = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    // A-15: all-time sends no params, so the default request is unchanged.
    const res = period.value === 'all'
      ? await api.get('/admin/platform-analytics/')
      : await api.get('/admin/platform-analytics/', { params: { period: period.value } });
    data.value = res.data;
    // NOTE: dateStyle/timeStyle cannot be combined with timeZoneName — the Intl spec
    // mandates a TypeError for that combination (in every compliant engine, browsers
    // included). It previously threw here on EVERY refresh, right after data was set,
    // so the catch below flipped fetchError=true and the dashboard always showed its
    // error state instead of the fetched data. Keep the short date+time; drop the
    // (invalid) timeZoneName. Regression guard: __tests__/AdminPlatformAnalytics.mount.test.js.
    // A-16: display the SERVER generation time (res.data.generated_at) — the payload
    // is cached 45 s server-side, so the client fetch clock would overstate freshness.
    // Fall back to the client clock only when the payload predates the field (a stale
    // cached entry served from before this field shipped).
    const generatedAt = res.data?.generated_at ? new Date(res.data.generated_at) : null;
    const stamp = generatedAt && !Number.isNaN(generatedAt.getTime()) ? generatedAt : new Date();
    refreshedAt.value = new Intl.DateTimeFormat(currentLocale.value, { dateStyle: 'short', timeStyle: 'short' }).format(stamp);
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(refresh);
</script>

<script>
/* eslint-disable vue/one-component-per-file --
   StatCard is a tiny presentational render-function helper used only on this
   page and is intentionally co-located with its colorMap. It is not a second
   page-level component. */
// Inline StatCard component — no separate file needed for this single-page use
import { defineComponent, h } from 'vue';
import { RouterLink } from 'vue-router';
import AppIcon from '../components/AppIcon.vue';

const colorMap = {
  sky: 'bg-sky-500/10 border-sky-500/20 text-sky-300',
  emerald: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300',
  amber: 'bg-amber-500/10 border-amber-500/20 text-amber-300',
  red: 'bg-red-500/10 border-red-500/20 text-red-300',
  violet: 'bg-violet-500/10 border-violet-500/20 text-violet-300',
};

const StatCard = defineComponent({
  name: 'StatCard',
  props: {
    value: { type: [String, Number], default: '—' },
    label: { type: String, required: true },
    // A-14: an AppIcon name (see ../components/AppIcon.vue) — never an emoji literal.
    icon: { type: String, default: '' },
    color: { type: String, default: 'sky' },
    // A-17: optional drill-down target (a vue-router location) for the admin list
    // behind this stat; cards without one stay plain display tiles.
    to: { type: [String, Object], default: null },
  },
  setup(props) {
    return () => {
      const inner = [
        h('div', { class: 'flex items-center gap-2' }, [
          props.icon ? h(AppIcon, { name: props.icon, class: 'h-5 w-5 shrink-0', 'aria-hidden': 'true' }) : null,
          h('span', { class: 'text-2xl font-bold tabular-nums' }, String(props.value ?? '—')),
        ]),
        h('p', { class: 'text-xs opacity-70 leading-snug' }, props.label),
      ];
      const cardClass = `rounded-2xl border p-4 flex flex-col gap-1 ${colorMap[props.color] || colorMap.sky}`;
      if (props.to) {
        return h(
          RouterLink,
          {
            to: props.to,
            class: `${cardClass} ui-press transition hover:brightness-125 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60`,
            'aria-label': props.label,
          },
          () => inner,
        );
      }
      return h(
        'div',
        { class: cardClass, role: 'group', 'aria-label': props.label },
        inner,
      );
    };
  },
});

export default { components: { StatCard } };
</script>
