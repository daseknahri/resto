<template>
  <div class="mx-auto w-full max-w-md px-4 py-5 space-y-4">
    <!-- Header -->
    <div class="space-y-0.5">
      <p class="ui-kicker">{{ t('driver.kicker') }}</p>
      <h1 class="ui-display text-2xl font-semibold text-white">{{ t('driver.title') }}</h1>
    </div>

    <!-- Loading -->
    <div v-if="!customerStore.loaded" class="ui-panel p-6">
      <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-emerald-400" />
    </div>

    <!-- Not signed in -->
    <div v-else-if="!customerStore.isAuthenticated" class="ui-panel p-5 space-y-3 text-center">
      <p class="text-sm text-slate-300">{{ t('driver.signInPrompt') }}</p>
      <RouterLink :to="{ name: 'customer-account' }" class="ui-btn-primary inline-flex px-5 py-2 text-sm">
        {{ t('driver.signInCta') }}
      </RouterLink>
    </div>

    <!-- Signed in but not yet a driver -->
    <div v-else-if="!isDriver" class="ui-panel p-5 space-y-3">
      <div class="flex items-center gap-2.5">
        <div class="flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10">
          <AppIcon name="truck" class="h-4.5 w-4.5 text-emerald-300" />
        </div>
        <p class="text-base font-semibold text-slate-100">{{ t('driver.becomeTitle') }}</p>
      </div>
      <p class="text-sm text-slate-400">{{ t('driver.becomeDesc') }}</p>

      <!-- Install the app first (drivers work from the installed app) -->
      <div v-if="!isStandalone && !continueInBrowser" class="rounded-xl border border-emerald-500/30 bg-emerald-500/8 p-3 space-y-2">
        <p class="text-sm font-semibold text-emerald-200">{{ t('driver.installTitle') }}</p>
        <p class="text-xs text-slate-300">{{ t('driver.installDesc') }}</p>
        <button v-if="canInstall" class="ui-btn-primary w-full py-2 text-sm" @click="promptInstall">
          {{ t('driver.installCta') }}
        </button>
        <p v-else class="text-xs text-slate-400">{{ t('driver.installManual') }}</p>
        <button class="text-[11px] text-slate-500 underline hover:text-slate-300" @click="continueInBrowser = true">
          {{ t('driver.continueInBrowser') }}
        </button>
      </div>

      <!-- Apply (after install, or after explicitly continuing in the browser) -->
      <template v-else>
        <div class="space-y-1">
          <label class="text-xs font-medium text-slate-400">{{ t('driver.vehicleLabel') }}</label>
          <input
            v-model.trim="vehicle"
            type="text"
            class="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-emerald-500 focus:outline-none"
            :placeholder="t('driver.vehiclePlaceholder')"
          />
        </div>
        <p v-if="errorMsg" class="text-xs text-red-300">{{ errorMsg }}</p>
        <button class="ui-btn-primary w-full px-5 py-2.5 text-sm" :disabled="busy" @click="becomeDriver">
          {{ busy ? '…' : t('driver.becomeCta') }}
        </button>
      </template>
    </div>

    <!-- Applied, awaiting admin approval -->
    <div v-else-if="!approved" class="ui-panel p-5 space-y-3 text-center">
      <div class="mx-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-amber-500/30 bg-amber-500/10">
        <AppIcon name="info" class="h-5 w-5 text-amber-300" />
      </div>
      <p class="text-base font-semibold text-slate-100">{{ t('driver.pendingTitle2') }}</p>
      <p class="text-sm text-slate-400">{{ t('driver.pendingDesc') }}</p>
      <button class="text-xs text-slate-400 hover:text-slate-200" :disabled="busy" @click="fetchStatus">
        {{ t('driver.refresh') }}
      </button>
    </div>

    <!-- Driver dashboard (approved) -->
    <template v-else>
      <!-- Online toggle -->
      <div class="ui-panel flex items-center justify-between gap-3 p-4">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <span class="h-2.5 w-2.5 rounded-full" :class="online ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'" />
            <p class="text-sm font-semibold" :class="online ? 'text-emerald-300' : 'text-slate-400'">
              {{ online ? t('driver.online') : t('driver.offline') }}
            </p>
          </div>
          <p class="mt-0.5 text-xs text-slate-500">{{ online ? t('driver.onlineHint') : t('driver.offlineHint') }}</p>
          <p v-if="geoError" class="mt-1 text-xs text-amber-300">{{ geoError }}</p>
        </div>
        <button
          class="shrink-0 rounded-full px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50"
          :class="online ? 'border border-slate-600 text-slate-300 hover:border-slate-400' : 'bg-emerald-600 text-white hover:bg-emerald-500'"
          :disabled="busy"
          @click="toggleOnline"
        >
          {{ online ? t('driver.goOffline') : t('driver.goOnline') }}
        </button>
      </div>

      <p v-if="errorMsg" class="rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2 text-sm text-red-300" role="alert">
        {{ errorMsg }}
      </p>

      <!-- Earnings summary -->
      <div v-if="earnings" class="ui-panel grid grid-cols-3 gap-2 p-4">
        <div class="text-center">
          <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('driver.earned') }}</p>
          <p class="mt-0.5 text-sm font-bold tabular-nums text-slate-200">{{ fmtMoney(earnings.earned) }}</p>
        </div>
        <div class="text-center">
          <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('driver.paidOut') }}</p>
          <p class="mt-0.5 text-sm font-bold tabular-nums text-slate-400">{{ fmtMoney(earnings.paid) }}</p>
        </div>
        <div class="text-center">
          <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('driver.owed') }}</p>
          <p class="mt-0.5 text-sm font-bold tabular-nums text-emerald-400">{{ fmtMoney(earnings.owed) }}</p>
        </div>
      </div>

      <!-- Cash-out: available wallet balance + redeem at a restaurant -->
      <div v-if="earnings" class="ui-panel p-4 space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('driver.available') }}</p>
            <p class="text-lg font-bold tabular-nums text-white">{{ fmtMoney(earnings.available) }}</p>
          </div>
          <button
            v-if="!cashout"
            class="ui-btn-primary px-3 py-1.5 text-xs disabled:opacity-50"
            :disabled="!earnings.can_cash_out || busy"
            @click="requestCashout"
          >{{ t('driver.cashOut') }}</button>
        </div>
        <p v-if="!earnings.can_cash_out && !cashout" class="text-[11px] text-slate-500">
          {{ t('driver.cashOutMin', { amount: fmtMoney(earnings.cashout_min) }) }}
        </p>
        <!-- Active cash-out request: show the code to read to a restaurant -->
        <div v-if="cashout" class="rounded-xl border border-emerald-500/30 bg-emerald-500/8 p-3 text-center">
          <p class="text-[11px] text-emerald-200">{{ t('driver.cashOutShowCode', { amount: fmtMoney(cashout.amount) }) }}</p>
          <p class="my-1 text-3xl font-bold tracking-[0.3em] text-white">{{ cashout.code }}</p>
          <button class="text-[11px] text-slate-400 underline hover:text-slate-200" :disabled="busy" @click="cancelCashout">
            {{ t('driver.cashOutCancel') }}
          </button>
        </div>
      </div>

      <!-- Active job -->
      <div v-if="activeJob" class="ui-panel p-4 space-y-3">
        <div class="flex items-center justify-between">
          <p class="text-sm font-semibold text-slate-200">{{ t('driver.activeTitle') }}</p>
          <span class="rounded-full bg-emerald-500/12 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
            {{ statusLabel(activeJob.status) }}
          </span>
        </div>
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p v-if="activeJob.restaurant_name" class="text-sm font-medium text-slate-200">{{ activeJob.restaurant_name }}</p>
          <p class="text-xs text-slate-500">{{ t('driver.order') }} #{{ activeJob.order_number }}</p>
        </div>
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
          <span v-if="activeJob.distance_km != null" class="inline-flex items-center gap-1">
            <AppIcon name="location" class="h-3 w-3" />{{ t('driver.distanceKm', { km: activeJob.distance_km }) }}
          </span>
          <span v-if="activeJob.items_count">{{ t('driver.itemsCount', { n: activeJob.items_count }) }}</span>
        </div>

        <!-- Cash to collect (COD) vs already paid — the driver must know -->
        <div
          v-if="activeJob.collect_cash"
          class="flex items-center justify-between rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2"
        >
          <span class="text-xs font-semibold text-amber-200">{{ t('driver.collectCash') }}</span>
          <span class="text-base font-bold tabular-nums text-amber-200">{{ fmtMoney(activeJob.order_total) }}</span>
        </div>
        <div
          v-else-if="activeJob.order_total"
          class="flex items-center gap-1.5 rounded-xl border border-emerald-600/30 bg-emerald-900/15 px-3 py-2 text-xs font-semibold text-emerald-300"
        >
          <AppIcon name="check" class="h-3.5 w-3.5" />{{ t('driver.prepaid', { amount: fmtMoney(activeJob.order_total) }) }}
        </div>

        <div class="space-y-2">
          <a
            v-if="activeJob.pickup_address || activeJob.pickup_lat"
            :href="mapsLink(activeJob.pickup_lat, activeJob.pickup_lng, activeJob.pickup_address)"
            target="_blank" rel="noopener"
            class="flex items-start gap-2.5 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5"
          >
            <AppIcon name="location" class="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
            <div class="min-w-0 flex-1">
              <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.pickup') }}</p>
              <p class="truncate text-sm text-slate-200">{{ activeJob.pickup_address || t('driver.openMaps') }}</p>
            </div>
            <AppIcon name="chevronRight" class="mt-1 h-4 w-4 shrink-0 text-slate-600" />
          </a>
          <a
            v-if="activeJob.delivery_address || activeJob.delivery_lat"
            :href="mapsLink(activeJob.delivery_lat, activeJob.delivery_lng, activeJob.delivery_address)"
            target="_blank" rel="noopener"
            class="flex items-start gap-2.5 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5"
          >
            <AppIcon name="location" class="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
            <div class="min-w-0 flex-1">
              <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.dropoff') }}</p>
              <p class="truncate text-sm text-slate-200">{{ activeJob.delivery_address || t('driver.openMaps') }}</p>
            </div>
            <AppIcon name="chevronRight" class="mt-1 h-4 w-4 shrink-0 text-slate-600" />
          </a>

          <!-- Call the customer (only the assigned driver sees the phone) -->
          <a
            v-if="activeJob.customer_phone"
            :href="`tel:${activeJob.customer_phone}`"
            class="flex items-center gap-2.5 rounded-xl border border-sky-700/50 bg-sky-900/20 px-3 py-2.5"
          >
            <AppIcon name="phone" class="h-4 w-4 shrink-0 text-sky-300" />
            <div class="min-w-0 flex-1">
              <p class="text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.callCustomer') }}</p>
              <p class="truncate text-sm text-slate-200">{{ activeJob.customer_name || activeJob.customer_phone }}</p>
            </div>
            <span class="text-xs font-semibold text-sky-300">{{ t('driver.call') }}</span>
          </a>
        </div>

        <!-- What's in the order -->
        <div v-if="activeJob.items && activeJob.items.length" class="rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2">
          <p class="mb-1 text-[11px] uppercase tracking-wider text-slate-500">{{ t('driver.itemsTitle') }}</p>
          <ul class="space-y-0.5">
            <li v-for="(it, idx) in activeJob.items" :key="idx" class="flex justify-between gap-2 text-sm text-slate-300">
              <span class="truncate">{{ it.name }}</span>
              <span class="shrink-0 tabular-nums text-slate-400">×{{ it.qty }}</span>
            </li>
          </ul>
        </div>

        <div class="flex items-center justify-between rounded-xl bg-slate-800/40 px-3 py-2">
          <span class="text-xs text-slate-400">{{ t('driver.payout') }}</span>
          <span class="text-sm font-semibold tabular-nums text-emerald-300">{{ fmtMoney(activeJob.driver_payout) }}</span>
        </div>

        <!-- Reminder: confirm delivery with the customer's code -->
        <p
          v-if="nextAction && nextAction.to === 'delivered'"
          class="flex items-start gap-1.5 rounded-lg bg-sky-900/15 px-2.5 py-1.5 text-[11px] text-sky-300"
        >
          <AppIcon name="info" class="mt-px h-3 w-3 shrink-0" />{{ t('driver.codeReminder') }}
        </p>

        <!-- Advance status -->
        <button
          v-if="nextAction"
          class="ui-btn-primary w-full px-5 py-2.5 text-sm"
          :disabled="busy"
          @click="advance(nextAction.to)"
        >
          {{ busy ? '…' : nextAction.label }}
        </button>
        <button
          v-if="!failingOpen"
          class="w-full rounded-xl border border-red-500/40 px-4 py-2 text-xs text-red-300 hover:border-red-400/70 hover:text-red-200 transition-colors disabled:opacity-50"
          :disabled="busy"
          @click="openFail"
        >
          {{ t('driver.actionFailed') }}
        </button>
        <!-- Failure-reason picker (the restaurant decides what happens next) -->
        <div v-else class="space-y-2 rounded-xl border border-red-500/40 bg-red-900/10 p-3">
          <p class="text-xs font-semibold text-red-200">{{ t('driver.failReasonTitle') }}</p>
          <button
            v-for="r in FAIL_REASONS"
            :key="r"
            class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-left text-sm text-slate-200 hover:border-slate-500 disabled:opacity-50"
            :disabled="busy"
            @click="submitFail(r)"
          >
            {{ t(`driver.failReason_${r}`) }}
          </button>
          <input
            v-model="failNote"
            :placeholder="t('driver.failNotePlaceholder')"
            class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-600"
          />
          <button class="w-full py-1 text-xs text-slate-400 hover:text-slate-200" :disabled="busy" @click="failingOpen = false">
            {{ t('driver.failCancel') }}
          </button>
        </div>
      </div>

      <!-- Pending jobs (only when online and free) -->
      <div v-else-if="online" class="ui-panel p-4 space-y-3">
        <div class="flex items-center justify-between">
          <p class="text-sm font-semibold text-slate-200">{{ t('driver.pendingTitle') }}</p>
          <button class="text-xs text-slate-400 hover:text-slate-200" :disabled="loadingJobs" @click="fetchJobs">
            {{ t('driver.refresh') }}
          </button>
        </div>
        <div v-if="loadingJobs && !pendingJobs.length" class="space-y-2">
          <div v-for="i in 2" :key="i" class="h-20 animate-pulse rounded-xl bg-slate-800/50" />
        </div>
        <p v-else-if="!pendingJobs.length" class="py-6 text-center text-sm text-slate-500">{{ t('driver.noPending') }}</p>
        <ul v-else class="space-y-2">
          <li v-for="job in pendingJobs" :key="job.id" class="rounded-xl border border-slate-700/60 bg-slate-900/40 p-3 space-y-2">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-slate-200">{{ job.restaurant_name || ('#' + job.order_number) }}</p>
                <p class="text-[11px] text-slate-500">{{ t('driver.order') }} #{{ job.order_number }}</p>
              </div>
              <span class="shrink-0 text-sm font-semibold tabular-nums text-emerald-300">{{ fmtMoney(job.driver_payout) }}</span>
            </div>
            <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400">
              <span v-if="job.distance_km != null" class="inline-flex items-center gap-1">
                <AppIcon name="location" class="h-3 w-3" />{{ t('driver.distanceKm', { km: job.distance_km }) }}
              </span>
              <span v-if="job.items_count">{{ t('driver.itemsCount', { n: job.items_count }) }}</span>
              <span v-if="job.collect_cash" class="rounded-full bg-amber-500/15 px-2 py-0.5 font-semibold text-amber-300">
                {{ t('driver.cashShort', { amount: fmtMoney(job.order_total) }) }}
              </span>
              <span v-else-if="job.order_total" class="rounded-full bg-emerald-500/12 px-2 py-0.5 font-semibold text-emerald-300">
                {{ t('driver.prepaidShort') }}
              </span>
            </div>
            <p v-if="job.delivery_address" class="truncate text-sm text-slate-300">
              <AppIcon name="location" class="mr-1 inline h-3.5 w-3.5 text-emerald-300" />{{ job.delivery_address }}
            </p>
            <button class="ui-btn-primary w-full px-4 py-2 text-sm" :disabled="busy" @click="accept(job.id)">
              {{ t('driver.accept') }}
            </button>
          </li>
        </ul>
      </div>

      <!-- Offline + no job -->
      <div v-else class="ui-panel p-6 text-center">
        <AppIcon name="truck" class="mx-auto h-8 w-8 text-slate-700" />
        <p class="mt-2 text-sm text-slate-500">{{ t('driver.offlineEmpty') }}</p>
      </div>

      <!-- Recent deliveries (history) -->
      <div class="ui-panel p-4 space-y-3">
        <button class="flex w-full items-center justify-between" :aria-expanded="showHistory" @click="toggleHistory">
          <p class="text-sm font-semibold text-slate-200">{{ t('driver.historyTitle') }}</p>
          <AppIcon :name="showHistory ? 'chevronUp' : 'chevronDown'" class="h-4 w-4 text-slate-500" />
        </button>
        <template v-if="showHistory">
          <div v-if="loadingHistory && !history.length" class="space-y-2">
            <div v-for="i in 3" :key="i" class="h-12 animate-pulse rounded-xl bg-slate-800/50" />
          </div>
          <p v-else-if="!history.length" class="py-4 text-center text-sm text-slate-500">{{ t('driver.historyEmpty') }}</p>
          <ul v-else class="space-y-2">
            <li v-for="d in history" :key="d.id" class="flex items-center justify-between gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2">
              <div class="min-w-0">
                <p class="truncate text-sm text-slate-200">{{ d.restaurant_name || ('#' + d.order_number) }}</p>
                <p class="text-[11px] text-slate-500">{{ statusLabel(d.status) }} · {{ fmtDate(d.delivered_at || d.failed_at || d.created_at) }}</p>
              </div>
              <span class="shrink-0 text-sm font-semibold tabular-nums" :class="d.status === 'delivered' ? 'text-emerald-300' : 'text-slate-500'">{{ fmtMoney(d.driver_payout) }}</span>
            </li>
          </ul>
        </template>
      </div>
    </template>
  </div>

  <!-- Rate the customer after delivery (driver → customer, private) -->
  <Teleport to="body">
    <div
      v-if="ratingJob"
      class="fixed inset-0 z-[2000] flex items-end justify-center bg-black/60 p-3 backdrop-blur-sm sm:items-center"
      @click.self="ratingJob = null"
      @keydown.esc="ratingJob = null"
    >
      <div class="w-full max-w-sm space-y-3 rounded-2xl border border-slate-700 bg-slate-900 p-4 shadow-2xl">
        <div>
          <p class="text-sm font-semibold text-white">{{ t('driver.rateCustomerTitle') }}</p>
          <p class="mt-0.5 text-xs text-slate-400">{{ t('driver.order') }} #{{ ratingJob.order_number }}</p>
          <p class="mt-1 text-[11px] text-slate-500">{{ t('driver.rateCustomerHint') }}</p>
        </div>
        <div class="flex items-center gap-1.5">
          <button
            v-for="n in 5" :key="n" type="button"
            class="text-3xl leading-none transition-transform hover:scale-110 focus:outline-none"
            :class="n <= custRatingScore ? 'text-amber-400' : 'text-slate-600'"
            :aria-label="t('common.rateNStars', { n })"
            @click="custRatingScore = n"
          >★</button>
        </div>
        <input
          v-model="custRatingNote" type="text" maxlength="200"
          class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none"
          :aria-label="t('driver.rateCustomerNote')"
          :placeholder="t('driver.rateCustomerNote')"
        />
        <div class="flex items-center justify-end gap-2 pt-1">
          <button class="px-3 py-2 text-xs font-medium text-slate-400 hover:text-slate-200" @click="ratingJob = null">
            {{ t('driver.rateSkip') }}
          </button>
          <button
            class="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            :disabled="!custRatingScore || submittingRating"
            @click="submitCustomerRating"
          >{{ submittingRating ? '…' : t('driver.rateSubmit') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import AppIcon from '../components/AppIcon.vue';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';
import { useToastStore } from '../stores/toast';
import { useCustomerPush } from '../composables/useCustomerPush';
import api from '../lib/api';

const { t, currentLocale } = useI18n();
const customerStore = useCustomerStore();
const toast = useToastStore();
const driverPush = useCustomerPush();

const isDriver = ref(false);
const approved = ref(false);
const vehicle = ref('');
const online = ref(false);
const activeJob = ref(null);
const pendingJobs = ref([]);

// ── Install-first PWA — drivers work from the installed app ──────────────────────
const isStandalone = ref(
  typeof window !== 'undefined' && (
    window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone === true
  )
);
const continueInBrowser = ref(false);
const canInstall = ref(false);
let deferredInstallPrompt = null;
const onBeforeInstallPrompt = (e) => {
  e.preventDefault();           // stash it so we can trigger our own button
  deferredInstallPrompt = e;
  canInstall.value = true;
};
const onAppInstalled = () => {
  canInstall.value = false;
  isStandalone.value = true;
};
const promptInstall = async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  try { await deferredInstallPrompt.userChoice; } catch { /* ignore */ }
  deferredInstallPrompt = null;
  canInstall.value = false;
};
const busy = ref(false);
const loadingJobs = ref(false);
const errorMsg = ref('');
const geoError = ref('');

let pollTimer = null;
let geoWatchId = null;
let lastPositionSent = 0;

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
    return new Date(iso).toLocaleDateString(currentLocale.value || undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
};

// Recent deliveries (history) — lazy-loaded the first time the driver expands it.
const showHistory = ref(false);
const history = ref([]);
const loadingHistory = ref(false);
const fetchHistory = async () => {
  loadingHistory.value = true;
  try {
    const { data } = await api.get('/driver/deliveries/');
    history.value = Array.isArray(data.results) ? data.results : [];
  } catch {
    /* keep last */
  } finally {
    loadingHistory.value = false;
  }
};
const toggleHistory = () => {
  showHistory.value = !showHistory.value;
  if (showHistory.value && !history.value.length) fetchHistory();
};

const STATUS_LABELS = {
  assigned: 'driver.statusAssigned',
  at_restaurant: 'driver.statusAtRestaurant',
  picked_up: 'driver.statusPickedUp',
  delivered: 'driver.statusDelivered',
  failed: 'driver.statusFailed',
};
const statusLabel = (s) => t(STATUS_LABELS[s] || 'driver.statusAssigned');

// Next forward transition for the active job's current status.
const NEXT = {
  assigned: { to: 'at_restaurant', label: 'driver.actionAtRestaurant' },
  at_restaurant: { to: 'picked_up', label: 'driver.actionPickedUp' },
  picked_up: { to: 'delivered', label: 'driver.actionDelivered' },
};
const nextAction = computed(() => {
  const n = activeJob.value && NEXT[activeJob.value.status];
  return n ? { to: n.to, label: t(n.label) } : null;
});

const mapsLink = (lat, lng, address) => {
  if (lat != null && lng != null) return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address || '')}`;
};

const earnings = ref(null);
const fetchEarnings = async () => {
  try {
    const { data } = await api.get('/driver/earnings/');
    earnings.value = data;
  } catch {
    earnings.value = null;
  }
};

// ── Cash-out: redeem wallet balance for cash at a restaurant ─────────────────────
const cashout = ref(null); // current pending request { id, amount, code, ... }
const fetchCashout = async () => {
  try {
    const { data } = await api.get('/driver/cashout/');
    cashout.value = data.pending || null;
  } catch {
    cashout.value = null;
  }
};
const requestCashout = async () => {
  errorMsg.value = '';
  const max = Number(earnings.value?.available || 0);
  const raw = window.prompt(t('driver.cashOutAmountPrompt', { max: fmtMoney(max) }), String(max));
  if (raw == null) return;
  const amount = Number(String(raw).replace(',', '.'));
  if (!Number.isFinite(amount) || amount <= 0) return;
  busy.value = true;
  try {
    const { data } = await api.post('/driver/cashout/', { amount });
    cashout.value = data;
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};
const cancelCashout = async () => {
  if (!cashout.value) return;
  busy.value = true;
  try {
    await api.post(`/driver/cashout/${cashout.value.id}/cancel/`);
    cashout.value = null;
  } catch {
    /* ignore */
  } finally {
    busy.value = false;
  }
};

const fetchStatus = async () => {
  try {
    const { data } = await api.get('/driver/status/');
    isDriver.value = Boolean(data.is_driver);
    approved.value = Boolean(data.driver_approved);
    online.value = Boolean(data.is_driver_online);
  } catch {
    isDriver.value = Boolean(customerStore.customer?.is_driver);
  }
};

const fetchJobs = async () => {
  if (!isDriver.value) return;
  loadingJobs.value = true;
  try {
    const { data } = await api.get('/driver/jobs/');
    activeJob.value = (data.active && data.active[0]) || null;
    pendingJobs.value = data.pending || [];
  } catch {
    /* keep last */
  } finally {
    loadingJobs.value = false;
  }
};

// Keep the job list fresh while the page is open (idempotent — never double-starts).
const ensurePoll = () => {
  if (!pollTimer) pollTimer = setInterval(fetchJobs, 15000);
};

const becomeDriver = async () => {
  errorMsg.value = '';
  busy.value = true;
  try {
    const { data } = await api.post('/driver/register/', { vehicle: vehicle.value });
    isDriver.value = Boolean(data.is_driver);
    approved.value = Boolean(data.driver_approved);
    online.value = Boolean(data.is_driver_online);
    if (customerStore.customer) customerStore.setCustomer({ ...customerStore.customer, is_driver: true });
    toast.show(approved.value ? t('driver.registered') : t('driver.applied'), 'success');
    if (approved.value) {
      await fetchJobs();
      ensurePoll();
    }
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

const toggleOnline = async () => {
  errorMsg.value = '';
  busy.value = true;
  const next = !online.value;
  try {
    const { data } = await api.patch('/driver/status/', { online: next });
    online.value = Boolean(data.is_driver_online);
    if (online.value) {
      startGeo();
      // Subscribe to web push so new jobs reach the driver even when backgrounded.
      driverPush.subscribe().catch(() => {});
      await fetchJobs();
    } else {
      stopGeo();
    }
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

const accept = async (jobId) => {
  errorMsg.value = '';
  busy.value = true;
  try {
    const { data } = await api.post(`/driver/jobs/${jobId}/accept/`, {});
    activeJob.value = data;
    pendingJobs.value = [];
  } catch (err) {
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
    await fetchJobs(); // someone else may have taken it
  } finally {
    busy.value = false;
  }
};

const advance = async (toStatus, extra = {}) => {
  errorMsg.value = '';
  const payload = { status: toStatus, ...extra };
  if (toStatus === 'delivered') {
    // Proof of delivery — the customer reads the code shown on their order.
    const code = (window.prompt(t('driver.enterDeliveryCode')) || '').trim();
    if (!code) return; // driver cancelled the prompt
    payload.code = code;
  }
  busy.value = true;
  try {
    const job = activeJob.value;
    const { data } = await api.patch(`/driver/jobs/${job.id}/status/`, payload);
    if (data.is_terminal) {
      activeJob.value = null;
      online.value = false; // backend takes the driver offline after delivery
      stopGeo();
      toast.show(t('driver.deliveredToast'), 'success');
      // The driver just met the customer — prompt them to rate the drop-off
      // while it's fresh (only on a successful delivery, not a failure).
      if (toStatus === 'delivered' && job && job.restaurant_slug) {
        openCustomerRating(job);
      }
      await fetchJobs();
      fetchEarnings(); // a completed delivery just added to earnings
    } else {
      activeJob.value = data;
    }
  } catch (err) {
    const errCode = err?.response?.data?.code;
    errorMsg.value = errCode === 'bad_delivery_code'
      ? t('driver.badDeliveryCode')
      : (err?.response?.data?.detail || t('driver.errorGeneric'));
  } finally {
    busy.value = false;
  }
};

const FAIL_REASONS = ['customer_no_show', 'bad_address', 'driver_unable', 'other'];
const failingOpen = ref(false);
const failNote = ref('');
const openFail = () => {
  failNote.value = '';
  failingOpen.value = true;
};
const submitFail = async (reason) => {
  failingOpen.value = false;
  await advance('failed', { failure_reason: reason, failure_note: failNote.value.trim() });
};

// ── Rate the customer (driver → customer, after delivery) ──────────────────────
const ratingJob = ref(null);
const custRatingScore = ref(0);
const custRatingNote = ref('');
const submittingRating = ref(false);

const openCustomerRating = (job) => {
  ratingJob.value = job;
  custRatingScore.value = 0;
  custRatingNote.value = '';
};

const submitCustomerRating = async () => {
  const job = ratingJob.value;
  if (!job || !custRatingScore.value || submittingRating.value) return;
  submittingRating.value = true;
  try {
    await api.post(
      `/marketplace/track/${job.order_number}/rate/?restaurant=${encodeURIComponent(job.restaurant_slug)}`,
      { role: 'driver', score: custRatingScore.value, note: custRatingNote.value },
    );
    ratingJob.value = null;
    toast.show(t('driver.ratingThanks'), 'success');
  } catch {
    toast.show(t('driver.ratingFailed'), 'error');
  } finally {
    submittingRating.value = false;
  }
};

// ── Geolocation ───────────────────────────────────────────────────────────────
const sendPosition = (lat, lng) => {
  const nowMs = Date.now();
  if (nowMs - lastPositionSent < 10000) return; // throttle to ~10s
  lastPositionSent = nowMs;
  api.post('/driver/position/', { lat, lng }).catch(() => {});
};

const startGeo = () => {
  geoError.value = '';
  if (!('geolocation' in navigator)) {
    geoError.value = t('driver.geoUnavailable');
    return;
  }
  if (geoWatchId !== null) return;
  geoWatchId = navigator.geolocation.watchPosition(
    (pos) => { geoError.value = ''; sendPosition(pos.coords.latitude, pos.coords.longitude); },
    () => { geoError.value = t('driver.locationDenied'); },
    { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
  );
};

const stopGeo = () => {
  if (geoWatchId !== null) {
    navigator.geolocation.clearWatch(geoWatchId);
    geoWatchId = null;
  }
};

onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.addEventListener('appinstalled', onAppInstalled);
  }
  await customerStore.fetchCustomer();
  if (!customerStore.isAuthenticated) return;
  await fetchStatus();
  if (isDriver.value && approved.value) {
    await fetchJobs();
    fetchEarnings();
    fetchCashout();
    if (online.value) {
      startGeo();
      driverPush.autoRestore().catch(() => {}); // re-arm push if previously opted in
    }
    ensurePoll();
  }
});

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer);
  stopGeo();
  if (typeof window !== 'undefined') {
    window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.removeEventListener('appinstalled', onAppInstalled);
  }
});
</script>
