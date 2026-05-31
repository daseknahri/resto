<template>
  <div class="p-6 space-y-8">
    <!-- Header -->
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminAnalytics.title') }}</h1>
        <p class="text-sm text-slate-400 mt-0.5">{{ t('adminAnalytics.subtitle') }}</p>
      </div>
      <button
        class="rounded-full border border-slate-700 px-4 py-2 text-xs text-slate-300 hover:border-slate-500 flex items-center gap-2"
        :disabled="loading"
        @click="refresh"
      >
        <span :class="loading ? 'animate-spin' : ''">↻</span>
        {{ t('adminAnalytics.refresh') }}
      </button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && !data" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
      <div v-for="i in 12" :key="i" class="h-24 rounded-2xl bg-slate-800/60 animate-pulse" />
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3" role="alert">
      <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('adminAnalytics.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="refresh"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Data -->
    <template v-else-if="data">
      <!-- Tenants -->
      <section>
        <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">{{ t('adminAnalytics.sectionTenants') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard :value="data.tenants.total" :label="t('adminAnalytics.totalTenants')" color="sky" icon="🏪" />
          <StatCard :value="data.tenants.active" :label="t('adminAnalytics.activeTenants')" color="emerald" icon="✅" />
          <StatCard :value="data.tenants.suspended" :label="t('adminAnalytics.suspendedTenants')" color="amber" icon="⏸" />
          <StatCard :value="data.tenants.canceled" :label="t('adminAnalytics.canceledTenants')" color="red" icon="✗" />
        </div>
      </section>

      <!-- Customers & Drivers -->
      <section>
        <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">{{ t('adminAnalytics.sectionCustomers') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <StatCard :value="data.customers.total" :label="t('adminAnalytics.totalCustomers')" color="violet" icon="👤" />
          <StatCard :value="data.customers.drivers_total" :label="t('adminAnalytics.totalDrivers')" color="sky" icon="🛵" />
          <StatCard :value="data.customers.drivers_online" :label="t('adminAnalytics.driversOnline')" color="emerald" icon="🟢" />
        </div>
      </section>

      <!-- Deliveries -->
      <section>
        <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">{{ t('adminAnalytics.sectionDeliveries') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          <StatCard :value="data.deliveries.total_jobs" :label="t('adminAnalytics.totalJobs')" color="sky" icon="📦" />
          <StatCard :value="data.deliveries.delivered" :label="t('adminAnalytics.deliveredJobs')" color="emerald" icon="✔" />
          <StatCard :value="data.deliveries.active" :label="t('adminAnalytics.activeJobs')" color="amber" icon="🔄" />
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

      <!-- Zones & Flash Sales side by side -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- Zones -->
        <section>
          <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">{{ t('adminAnalytics.sectionZones') }}</h2>
          <div class="grid grid-cols-2 gap-4">
            <StatCard :value="data.zones.total" :label="t('adminAnalytics.totalZones')" color="sky" icon="🗺" />
            <StatCard :value="data.zones.active" :label="t('adminAnalytics.activeZones')" color="emerald" icon="✅" />
          </div>
        </section>

        <!-- Flash Sales -->
        <section>
          <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">{{ t('adminAnalytics.sectionFlashSales') }}</h2>
          <div class="grid grid-cols-3 gap-4">
            <StatCard :value="data.flash_sales.total" :label="t('adminAnalytics.totalSales')" color="sky" icon="⚡" />
            <StatCard :value="data.flash_sales.live" :label="t('adminAnalytics.liveSales')" color="emerald" icon="🔴" />
            <StatCard :value="data.flash_sales.total_redemptions" :label="t('adminAnalytics.redemptions')" color="amber" icon="🎟" />
          </div>
        </section>
      </div>

      <!-- Wallet -->
      <section>
        <h2 class="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">{{ t('adminAnalytics.sectionWallet') }}</h2>
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
      <p class="text-[11px] text-slate-600 text-right">{{ t('adminAnalytics.lastRefreshed') }} {{ refreshedAt }}</p>
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
  return new Intl.NumberFormat(currentLocale.value, { style: 'currency', currency: 'EUR', minimumFractionDigits: 2 }).format(val);
};

const refresh = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/admin/platform-analytics/');
    data.value = res.data;
    refreshedAt.value = new Intl.DateTimeFormat(currentLocale.value, { timeStyle: 'short' }).format(new Date());
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(refresh);
</script>

<script>
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
      { class: `rounded-2xl border p-4 flex flex-col gap-1 ${colorMap[props.color] || colorMap.sky}` },
      [
        h('div', { class: 'flex items-center gap-2' }, [
          props.icon ? h('span', { class: 'text-lg leading-none' }, props.icon) : null,
          h('span', { class: 'text-2xl font-bold tabular-nums' }, String(props.value ?? '—')),
        ]),
        h('p', { class: 'text-xs opacity-70 leading-snug' }, props.label),
      ],
    );
  },
});

export default { components: { StatCard } };
</script>
