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
          <StatCard :value="currency(data.financials.customer_wallet_liability)" :label="t('adminAnalytics.walletLiability')" color="violet" icon="👛" />
          <StatCard :value="currency(data.financials.restaurant_float_outstanding)" :label="t('adminAnalytics.floatOutstanding')" color="sky" icon="🏪" />
          <StatCard :value="currency(data.financials.driver_owed)" :label="t('adminAnalytics.driverOwed')" color="emerald" icon="🛵" />
        </div>
        <p class="text-[11px] text-slate-500">{{ t('adminAnalytics.financialsHint') }}</p>
      </section>

      <!-- Restaurants -->
      <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '28ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionTenants') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard :value="data.tenants.total" :label="t('adminAnalytics.totalTenants')" color="sky" icon="🏪" />
          <StatCard :value="data.tenants.active" :label="t('adminAnalytics.activeTenants')" color="emerald" icon="✅" />
          <StatCard :value="data.tenants.suspended" :label="t('adminAnalytics.suspendedTenants')" color="amber" icon="⏸" />
          <StatCard :value="data.tenants.canceled" :label="t('adminAnalytics.canceledTenants')" color="red" icon="✗" />
        </div>
      </section>

      <!-- Customers & Drivers -->
      <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '56ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionCustomers') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <StatCard :value="data.customers.total" :label="t('adminAnalytics.totalCustomers')" color="violet" icon="👤" />
          <StatCard :value="data.customers.drivers_total" :label="t('adminAnalytics.totalDrivers')" color="sky" icon="🛵" />
          <StatCard :value="data.customers.drivers_online" :label="t('adminAnalytics.driversOnline')" color="emerald" icon="🟢" />
        </div>
      </section>

      <!-- Deliveries -->
      <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '84ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionDeliveries') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          <StatCard :value="data.deliveries.total_jobs" :label="t('adminAnalytics.totalJobs')" color="sky" icon="📦" />
          <StatCard :value="data.deliveries.delivered" :label="t('adminAnalytics.deliveredJobs')" color="emerald" icon="✔" />
          <StatCard :value="data.deliveries.active" :label="t('adminAnalytics.activeJobs')" color="amber" icon="🔄" />
          <StatCard :value="data.deliveries.searching" :label="t('adminAnalytics.searchingJobs')" color="sky" icon="🔍" />
          <StatCard :value="data.deliveries.failed" :label="t('adminAnalytics.failedJobs')" color="red" icon="✗" />
          <StatCard
            :value="data.deliveries.avg_driver_rating != null ? data.deliveries.avg_driver_rating + ' ★' : '—'"
            :label="t('adminAnalytics.avgDriverRating')"
            color="amber"
            icon="⭐"
          />
          <StatCard
            :value="data.deliveries.total_fees != null ? currency(data.deliveries.total_fees) : '—'"
            :label="t('adminAnalytics.totalFees')"
            color="sky"
            icon="💰"
          />
          <StatCard
            :value="data.deliveries.total_driver_payouts != null ? currency(data.deliveries.total_driver_payouts) : '—'"
            :label="t('adminAnalytics.totalPayouts')"
            color="violet"
            icon="💸"
          />
        </div>
      </section>

      <!-- Rides -->
      <section v-if="data.rides" class="ui-reveal space-y-3" :style="{ '--ui-delay': '98ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.ridesTitle') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard :value="data.rides.total" :label="t('adminAnalytics.ridesTotal')" color="sky" icon="🚗" />
          <StatCard :value="data.rides.completed" :label="t('adminAnalytics.ridesCompleted')" color="emerald" icon="✔" />
          <StatCard :value="data.rides.active" :label="t('adminAnalytics.ridesActive')" color="amber" icon="🔄" />
          <StatCard :value="data.rides.cancelled" :label="t('adminAnalytics.ridesCancelled')" color="red" icon="✗" />
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <StatCard
            :value="data.rides.fare_gmv != null ? currency(data.rides.fare_gmv) : '—'"
            :label="t('adminAnalytics.ridesGmv')"
            color="violet"
            icon="💰"
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
            <StatCard :value="data.zones.total" :label="t('adminAnalytics.totalZones')" color="sky" icon="🗺" />
            <StatCard :value="data.zones.active" :label="t('adminAnalytics.activeZones')" color="emerald" icon="✅" />
          </div>
        </section>

        <!-- Flash Sales -->
        <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '112ms' }">
          <h2 class="ui-kicker">{{ t('adminAnalytics.sectionFlashSales') }}</h2>
          <div class="grid grid-cols-3 gap-4">
            <StatCard :value="data.flash_sales.total" :label="t('adminAnalytics.totalSales')" color="sky" icon="⚡" />
            <StatCard :value="data.flash_sales.live" :label="t('adminAnalytics.liveSales')" color="emerald" icon="🔴" />
            <StatCard :value="data.flash_sales.total_redemptions" :label="t('adminAnalytics.redemptions')" color="amber" icon="🎟" />
          </div>
        </section>
      </div>

      <!-- Wallet -->
      <section class="ui-reveal space-y-3" :style="{ '--ui-delay': '140ms' }">
        <h2 class="ui-kicker">{{ t('adminAnalytics.sectionWallet') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard
            :value="data.wallet.total_balance != null ? currency(data.wallet.total_balance) : '—'"
            :label="t('adminAnalytics.totalBalance')"
            color="emerald"
            icon="👛"
          />
          <StatCard :value="data.wallet.total_transactions" :label="t('adminAnalytics.totalTxns')" color="sky" icon="🔁" />
          <StatCard
            :value="data.wallet.total_bonus_issued != null ? currency(data.wallet.total_bonus_issued) : '—'"
            :label="t('adminAnalytics.bonusIssued')"
            color="amber"
            icon="🎁"
          />
          <StatCard
            :value="data.wallet.total_payments != null ? currency(data.wallet.total_payments) : '—'"
            :label="t('adminAnalytics.payments')"
            color="violet"
            icon="💳"
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

const currency = (val) => {
  if (val == null) return '—';
  return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'MAD', minimumFractionDigits: 2 }).format(val);
};

const refresh = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/admin/platform-analytics/');
    data.value = res.data;
    refreshedAt.value = new Intl.DateTimeFormat(currentLocale.value, { dateStyle: 'short', timeStyle: 'short', timeZoneName: 'short' }).format(new Date());
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
    icon: { type: String, default: '' },
    color: { type: String, default: 'sky' },
  },
  setup(props) {
    return () => h(
      'div',
      { class: `rounded-2xl border p-4 flex flex-col gap-1 ${colorMap[props.color] || colorMap.sky}`, role: 'group', 'aria-label': props.label },
      [
        h('div', { class: 'flex items-center gap-2' }, [
          props.icon ? h('span', { class: 'text-lg leading-none', 'aria-hidden': 'true' }, props.icon) : null,
          h('span', { class: 'text-2xl font-bold tabular-nums' }, String(props.value ?? '—')),
        ]),
        h('p', { class: 'text-xs opacity-70 leading-snug' }, props.label),
      ],
    );
  },
});

export default { components: { StatCard } };
</script>
