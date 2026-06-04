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
      <p v-if="errorMsg" class="text-xs text-red-300">{{ errorMsg }}</p>
      <button class="ui-btn-primary w-full px-5 py-2.5 text-sm" :disabled="busy" @click="becomeDriver">
        {{ busy ? '…' : t('driver.becomeCta') }}
      </button>
    </div>

    <!-- Driver dashboard -->
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

      <!-- Active job -->
      <div v-if="activeJob" class="ui-panel p-4 space-y-3">
        <div class="flex items-center justify-between">
          <p class="text-sm font-semibold text-slate-200">{{ t('driver.activeTitle') }}</p>
          <span class="rounded-full bg-emerald-500/12 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
            {{ statusLabel(activeJob.status) }}
          </span>
        </div>
        <p class="text-xs text-slate-500">{{ t('driver.order') }} #{{ activeJob.order_number }}</p>

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

        <div class="flex items-center justify-between rounded-xl bg-slate-800/40 px-3 py-2">
          <span class="text-xs text-slate-400">{{ t('driver.payout') }}</span>
          <span class="text-sm font-semibold tabular-nums text-emerald-300">{{ fmtMoney(activeJob.driver_payout) }}</span>
        </div>

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
          class="w-full rounded-xl border border-red-500/40 px-4 py-2 text-xs text-red-300 hover:border-red-400/70 hover:text-red-200 transition-colors disabled:opacity-50"
          :disabled="busy"
          @click="markFailed"
        >
          {{ t('driver.actionFailed') }}
        </button>
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
            <div class="flex items-center justify-between gap-2">
              <p class="text-xs text-slate-500">{{ t('driver.order') }} #{{ job.order_number }}</p>
              <span class="text-sm font-semibold tabular-nums text-emerald-300">{{ fmtMoney(job.driver_payout) }}</span>
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
const online = ref(false);
const activeJob = ref(null);
const pendingJobs = ref([]);
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

const fetchStatus = async () => {
  try {
    const { data } = await api.get('/driver/status/');
    isDriver.value = Boolean(data.is_driver);
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
    const { data } = await api.post('/driver/register/', {});
    isDriver.value = Boolean(data.is_driver);
    online.value = Boolean(data.is_driver_online);
    if (customerStore.customer) customerStore.setCustomer({ ...customerStore.customer, is_driver: true });
    toast.show(t('driver.registered'), 'success');
    await fetchJobs();
    ensurePoll();
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

const advance = async (toStatus) => {
  errorMsg.value = '';
  busy.value = true;
  try {
    const job = activeJob.value;
    const { data } = await api.patch(`/driver/jobs/${job.id}/status/`, { status: toStatus });
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
    errorMsg.value = err?.response?.data?.detail || t('driver.errorGeneric');
  } finally {
    busy.value = false;
  }
};

const markFailed = async () => {
  if (!window.confirm(t('driver.failConfirm'))) return;
  await advance('failed');
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
  await customerStore.fetchCustomer();
  if (!customerStore.isAuthenticated) return;
  await fetchStatus();
  if (isDriver.value) {
    await fetchJobs();
    fetchEarnings();
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
});
</script>
