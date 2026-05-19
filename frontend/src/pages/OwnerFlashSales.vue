<template>
  <div class="space-y-6 pb-6">

    <!-- Header -->
    <div>
      <p class="ui-kicker">{{ t('ownerFlashSales.kicker') }}</p>
      <h1 class="text-2xl font-bold text-white">{{ t('ownerFlashSales.title') }}</h1>
      <p class="mt-1 text-sm text-slate-400">{{ t('ownerFlashSales.subtitle') }}</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-16 text-center text-sm text-slate-400">
      {{ t('ownerFlashSales.loading') }}
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="py-16 text-center text-sm text-red-300">
      {{ t('ownerFlashSales.fetchError') }}
    </div>

    <!-- Empty -->
    <div v-else-if="!sales.length" class="py-16 text-center space-y-2">
      <p class="text-3xl">⚡</p>
      <p class="text-base font-semibold text-slate-300">{{ t('ownerFlashSales.empty') }}</p>
      <p class="text-sm text-slate-500">{{ t('ownerFlashSales.emptyHint') }}</p>
    </div>

    <!-- Sales list -->
    <ul v-else class="space-y-4">
      <li
        v-for="sale in sales"
        :key="sale.id"
        class="rounded-2xl border border-slate-700/60 bg-slate-900/60 p-5 transition-colors hover:border-slate-600"
      >
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <!-- Info -->
          <div class="min-w-0 flex-1 space-y-1.5">
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="text-sm font-bold text-slate-100">{{ sale.name }}</h2>
              <!-- Live badge -->
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="sale.is_live
                  ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                  : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
              >
                {{ sale.is_live ? t('ownerFlashSales.live') : t('ownerFlashSales.notLive') }}
              </span>
              <!-- Opted-in badge -->
              <span
                v-if="sale.opted_in"
                class="rounded-full border border-violet-500/30 bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold text-violet-300"
              >
                ✓ {{ t('ownerFlashSales.optedIn') }}
              </span>
            </div>

            <p v-if="sale.description" class="text-xs text-slate-400">{{ sale.description }}</p>

            <!-- Discount + dates -->
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
              <span class="font-semibold text-[var(--color-secondary,#f59e0b)]">
                ⚡ {{ sale.discount_value }}% {{ t('ownerFlashSales.off') }}
              </span>
              <span>
                {{ t('ownerFlashSales.from') }}
                {{ formatDate(sale.active_from) }}
                {{ t('ownerFlashSales.to') }}
                {{ formatDate(sale.active_until) }}
              </span>
              <span v-if="sale.max_redemptions">
                {{ t('ownerFlashSales.redemptions', { count: sale.redemption_count, max: sale.max_redemptions }) }}
              </span>
              <span v-else class="text-slate-500">
                {{ t('ownerFlashSales.redemptionsUnlimited', { count: sale.redemption_count }) }}
              </span>
            </div>
          </div>

          <!-- Opt-in toggle -->
          <div class="shrink-0">
            <button
              v-if="!sale.opted_in"
              class="rounded-full bg-[var(--color-secondary,#f59e0b)] px-4 py-2 text-xs font-semibold text-slate-950 transition-opacity hover:opacity-90 disabled:opacity-50"
              :disabled="toggling === sale.id"
              @click="optIn(sale)"
            >
              {{ toggling === sale.id ? '…' : t('ownerFlashSales.optIn') }}
            </button>
            <button
              v-else
              class="rounded-full border border-slate-600 px-4 py-2 text-xs font-semibold text-slate-300 transition-colors hover:border-red-500/50 hover:text-red-300 disabled:opacity-50"
              :disabled="toggling === sale.id"
              @click="optOut(sale)"
            >
              {{ toggling === sale.id ? '…' : t('ownerFlashSales.optOut') }}
            </button>
          </div>
        </div>
      </li>
    </ul>

    <!-- How it works info box -->
    <div class="rounded-2xl border border-slate-700/40 bg-slate-900/30 p-5">
      <h3 class="mb-2 text-sm font-semibold text-slate-200">{{ t('ownerFlashSales.howItWorksTitle') }}</h3>
      <ul class="space-y-1.5 text-xs text-slate-400">
        <li>⚡ {{ t('ownerFlashSales.howItWorks1') }}</li>
        <li>🛒 {{ t('ownerFlashSales.howItWorks2') }}</li>
        <li>💰 {{ t('ownerFlashSales.howItWorks3') }}</li>
        <li>📊 {{ t('ownerFlashSales.howItWorks4') }}</li>
      </ul>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import { useToastStore } from '../stores/toast';

const { t } = useI18n();
const toast = useToastStore();

const loading = ref(true);
const fetchError = ref(false);
const sales = ref([]);
const toggling = ref(null); // sale.id currently being toggled

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return iso.slice(0, 10);
  }
};

const fetchSales = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/owner/flash-sales/');
    sales.value = res.data;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const optIn = async (sale) => {
  toggling.value = sale.id;
  try {
    await api.post(`/owner/flash-sales/${sale.id}/opt-in/`);
    sale.opted_in = true;
    toast.show(t('ownerFlashSales.optInSuccess'));
  } catch {
    toast.show(t('ownerFlashSales.optInError'), 'error');
  } finally {
    toggling.value = null;
  }
};

const optOut = async (sale) => {
  toggling.value = sale.id;
  try {
    await api.delete(`/owner/flash-sales/${sale.id}/opt-in/`);
    sale.opted_in = false;
    toast.show(t('ownerFlashSales.optOutSuccess'));
  } catch {
    toast.show(t('ownerFlashSales.optOutError'), 'error');
  } finally {
    toggling.value = null;
  }
};

onMounted(fetchSales);
</script>
