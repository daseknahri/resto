<template>
  <div class="ui-safe-bottom min-h-screen bg-slate-950">

    <!-- ══════════════════════════ LOADING ══════════════════════════ -->
    <div
      v-if="!customerStore.loaded"
      class="flex min-h-[65vh] flex-col items-center justify-center gap-5 px-4"
      aria-busy="true"
      :aria-label="t('common.loading')"
    >
      <div class="h-16 w-16 animate-pulse rounded-3xl border border-slate-700/60 bg-slate-900/60" />
      <div class="mx-auto h-4 w-32 animate-pulse rounded-lg bg-slate-800" />
    </div>

    <!-- ══════════════════════════ NOT SIGNED IN ══════════════════════════ -->
    <template v-else-if="!customerStore.isAuthenticated">
      <div class="relative overflow-hidden bg-slate-950 ui-reveal">
        <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_-10%,rgba(99,102,241,0.13),transparent_65%)]" />
        <div class="relative px-4 pb-10 pt-12 text-center space-y-5">
          <div class="mx-auto flex h-20 w-20 items-center justify-center rounded-[22px] border border-slate-700/60 bg-gradient-to-br from-slate-800/80 to-slate-900/80 shadow-xl">
            <AppIcon name="truck" class="h-9 w-9 text-indigo-400" aria-hidden="true" />
          </div>
          <div class="space-y-2">
            <p class="ui-kicker">{{ t('ridePage.kicker') }}</p>
            <h1 class="ui-page-title">{{ t('ridePage.title') }}</h1>
            <p class="ui-subtle mx-auto max-w-xs leading-relaxed">{{ t('ridePage.signInFirst') }}</p>
          </div>
          <button
            class="ui-btn-primary ui-touch-target mx-auto gap-2 px-6"
            @click="showAuthModal = true"
          >
            <AppIcon name="user" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t('customerAccount.signIn') }}
          </button>
        </div>
      </div>
      <CustomerAuthModal
        v-if="showAuthModal"
        @close="showAuthModal = false"
        @authenticated="showAuthModal = false"
      />
    </template>

    <!-- ══════════════════════════ SIGNED IN ══════════════════════════ -->
    <template v-else>

      <!-- ── Page header ── -->
      <header class="relative overflow-hidden bg-slate-950 pb-4 pt-6 ui-reveal">
        <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-indigo-500/7 via-transparent to-transparent" />
        <div class="relative px-4">
          <p class="ui-kicker">{{ t('ridePage.kicker') }}</p>
          <h1 class="ui-page-title flex items-center gap-2">
            <AppIcon name="truck" class="h-5 w-5 text-indigo-400" aria-hidden="true" />
            {{ t('ridePage.title') }}
          </h1>
        </div>
      </header>

      <!-- ══════════════════════════ ACTIVE RIDE TRACKING ══════════════════════════ -->
      <div
        v-if="activeRide && activeRide.status !== 'completed' && activeRide.status !== 'cancelled'"
        class="px-3 pb-6 space-y-3"
        aria-live="polite"
        aria-atomic="false"
      >
        <!-- Status banner -->
        <div
          class="ui-panel ui-reveal relative overflow-hidden p-4 space-y-3"
          :class="{
            'border-amber-500/30 bg-amber-500/6': activeRide.status === 'searching',
            'border-sky-500/30 bg-sky-500/6': activeRide.status === 'accepted',
            'border-violet-500/30 bg-violet-500/6': activeRide.status === 'arrived',
            'border-emerald-500/30 bg-emerald-500/6': activeRide.status === 'in_progress',
          }"
        >
          <!-- Pulse ring for active states -->
          <div
            class="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset motion-safe:animate-pulse"
            :class="{
              'ring-amber-500/15': activeRide.status === 'searching',
              'ring-sky-500/15': activeRide.status === 'accepted',
              'ring-violet-500/15': activeRide.status === 'arrived',
              'ring-emerald-500/15': activeRide.status === 'in_progress',
            }"
            aria-hidden="true"
          />

          <!-- Status label -->
          <div class="relative flex items-center gap-3">
            <span
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border"
              :class="{
                'border-amber-500/40 bg-amber-500/12 text-amber-300': activeRide.status === 'searching',
                'border-sky-500/40 bg-sky-500/12 text-sky-300': activeRide.status === 'accepted',
                'border-violet-500/40 bg-violet-500/12 text-violet-300': activeRide.status === 'arrived',
                'border-emerald-500/40 bg-emerald-500/12 text-emerald-300': activeRide.status === 'in_progress',
              }"
              aria-hidden="true"
            >
              <AppIcon name="truck" class="h-4 w-4" aria-hidden="true" />
            </span>
            <div class="min-w-0 flex-1">
              <p
                class="text-sm font-semibold"
                :class="{
                  'text-amber-300': activeRide.status === 'searching',
                  'text-sky-300': activeRide.status === 'accepted',
                  'text-violet-300': activeRide.status === 'arrived',
                  'text-emerald-300': activeRide.status === 'in_progress',
                }"
              >
                {{ rideStatusLabel }}
              </p>
              <p v-if="activeRide.driver" class="mt-0.5 text-xs text-slate-400">
                {{ activeRide.driver.name }}
                <span v-if="activeRide.driver.driver_vehicle" class="ms-1 text-slate-500">· {{ activeRide.driver.driver_vehicle }}</span>
              </p>
            </div>
            <!-- Phone link once driver assigned -->
            <a
              v-if="activeRide.driver?.phone"
              :href="`tel:${activeRide.driver.phone}`"
              class="ui-btn-outline ui-touch-target ui-press shrink-0 gap-1.5 px-3 py-2 text-xs"
              :aria-label="t('deliveryTracker.call')"
            >
              <AppIcon name="phone" class="h-4 w-4" aria-hidden="true" />
            </a>
          </div>

          <!-- Addresses -->
          <dl class="ui-admin-subcard space-y-1 px-3 py-2 relative">
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.pickupLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activeRide.pickup_address }}</dd>
            </div>
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.dropoffLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activeRide.dropoff_address }}</dd>
            </div>
          </dl>
        </div>

        <!-- Live map (driver position) -->
        <div
          v-show="hasDriverPos"
          ref="trackingMapEl"
          class="h-52 w-full overflow-hidden rounded-2xl border border-slate-800"
          role="img"
          :aria-label="t('ridePage.driverAssigned')"
        />

        <!-- Cancel button (searching / accepted) -->
        <button
          v-if="activeRide.status === 'searching' || activeRide.status === 'accepted'"
          type="button"
          class="w-full rounded-2xl border border-red-500/30 bg-red-500/8 py-3 text-sm font-semibold text-red-300 transition hover:bg-red-500/15 ui-press disabled:opacity-50"
          :disabled="cancelling"
          @click="cancelRide"
        >
          {{ cancelling ? t('common.loading') : t('ridePage.cancelCta') }}
        </button>
      </div>

      <!-- ══════════════════════════ COMPLETED — RATE ══════════════════════════ -->
      <div
        v-else-if="activeRide && activeRide.status === 'completed'"
        class="px-3 pb-6 space-y-3"
      >
        <div class="ui-panel ui-reveal p-4 space-y-3 border-emerald-500/30 bg-emerald-500/6">
          <p class="ui-kicker">{{ t('ridePage.completed') }}</p>
          <dl class="space-y-1">
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.pickupLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activeRide.pickup_address }}</dd>
            </div>
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.dropoffLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activeRide.dropoff_address }}</dd>
            </div>
          </dl>
        </div>

        <!-- Rating UI -->
        <div v-if="!ratingDone" class="ui-panel ui-reveal p-4 space-y-3">
          <p class="ui-kicker">{{ t('ridePage.rateTitle') }}</p>
          <div class="flex justify-center gap-1" role="radiogroup" :aria-label="t('ridePage.rateTitle')">
            <button
              v-for="n in 5"
              :key="n"
              type="button"
              role="radio"
              class="ui-touch-target ui-press flex items-center justify-center rounded-xl transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              :class="ratingScore >= n ? 'text-amber-400' : 'text-slate-600 hover:text-slate-400'"
              :aria-label="`${n} star${n > 1 ? 's' : ''}`"
              :aria-checked="ratingScore === n"
              @click="ratingScore = n"
            >
              <AppIcon name="star" class="h-8 w-8" aria-hidden="true" />
            </button>
          </div>
          <button
            type="button"
            class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold disabled:opacity-50"
            :disabled="!ratingScore || submittingRating"
            @click="submitRating"
          >
            {{ submittingRating ? t('common.saving') : t('ridePage.rateCta') }}
          </button>
        </div>
        <p
          v-else
          role="status"
          class="flex items-center justify-center gap-2 rounded-2xl border border-emerald-500/25 bg-emerald-500/8 py-4 text-sm font-semibold text-emerald-300"
        >
          <AppIcon name="check" class="h-4 w-4 shrink-0" aria-hidden="true" />
          {{ t('ridePage.rated') }}
        </p>

        <!-- Book another -->
        <button
          type="button"
          class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold"
          @click="resetForm"
        >
          {{ t('ridePage.title') }}
        </button>
      </div>

      <!-- ══════════════════════════ CANCELLED ══════════════════════════ -->
      <div
        v-else-if="showCancelled"
        class="px-3 pb-6 space-y-3"
      >
        <div class="ui-panel ui-reveal p-4 border-red-500/25 bg-red-500/6 space-y-3">
          <p class="text-sm font-semibold text-red-300">{{ t('ridePage.cancelled') }}</p>
        </div>
        <button
          type="button"
          class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold"
          @click="resetForm"
        >
          {{ t('ridePage.title') }}
        </button>
      </div>

      <!-- ══════════════════════════ BOOKING FORM ══════════════════════════ -->
      <div
        v-else
        class="px-3 pb-28 space-y-3"
      >
        <!-- No-driver-found notice (system cancel detected by polling) -->
        <div
          v-if="noDriverFound"
          role="alert"
          class="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/8 px-4 py-3"
        >
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-amber-200">{{ t('ridePage.noDriverFound') }}</p>
          <button
            type="button"
            class="shrink-0 text-amber-400 hover:text-amber-300"
            :aria-label="t('common.close')"
            @click="noDriverFound = false"
          >
            <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <!-- Error banners -->
        <div
          v-if="errorMsg"
          role="alert"
          class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3"
        >
          <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
          <p class="flex-1 text-sm text-red-300">{{ errorMsg }}</p>
          <button
            type="button"
            class="shrink-0 text-red-400 hover:text-red-300"
            :aria-label="t('common.close')"
            @click="errorMsg = ''"
          >
            <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <!-- ── Pickup ── -->
        <section class="ui-panel ui-reveal p-4 space-y-3">
          <p class="ui-kicker flex items-center gap-1.5">
            <AppIcon name="location" class="h-3.5 w-3.5 text-[var(--color-secondary)]" aria-hidden="true" />
            {{ t('ridePage.pickupLabel') }}
          </p>
          <button
            type="button"
            class="w-full inline-flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2.5 text-sm text-slate-300 transition hover:border-[var(--color-secondary)]/40 hover:bg-[var(--color-secondary)]/5 ui-press"
            :class="locating ? 'opacity-60' : ''"
            :disabled="locating"
            @click="useMyLocation"
          >
            <AppIcon name="location" class="h-4 w-4 shrink-0 text-[var(--color-secondary)]" aria-hidden="true" />
            <span class="flex-1 text-left text-sm">{{ locating ? t('common.loading') : t('ridePage.useMyLocation') }}</span>
          </button>
          <input
            v-model="pickupAddress"
            type="text"
            class="ui-input w-full"
            :placeholder="t('ridePage.addressPlaceholder')"
            :aria-label="t('ridePage.pickupLabel')"
          />
          <p v-if="pickupLatLng" class="text-[11px] text-emerald-400 flex items-center gap-1">
            <AppIcon name="check" class="h-3 w-3" aria-hidden="true" />
            {{ pickupLatLng.lat.toFixed(5) }}, {{ pickupLatLng.lng.toFixed(5) }}
          </p>
        </section>

        <!-- ── Drop-off + map ── -->
        <section class="ui-panel ui-reveal p-4 space-y-3">
          <p class="ui-kicker flex items-center gap-1.5">
            <AppIcon name="location" class="h-3.5 w-3.5 text-indigo-400" aria-hidden="true" />
            {{ t('ridePage.dropoffLabel') }}
          </p>
          <input
            v-model="dropoffAddress"
            type="text"
            class="ui-input w-full"
            :placeholder="t('ridePage.addressPlaceholder')"
            :aria-label="t('ridePage.dropoffLabel')"
          />
          <!-- Leaflet map — tap to place drop-off pin -->
          <div
            ref="pickMapEl"
            class="h-48 w-full overflow-hidden rounded-xl border border-slate-800"
            role="img"
            :aria-label="t('ridePage.dropoffLabel')"
          />
          <p v-if="dropoffLatLng" class="text-[11px] text-indigo-300 flex items-center gap-1">
            <AppIcon name="check" class="h-3 w-3" aria-hidden="true" />
            {{ dropoffLatLng.lat.toFixed(5) }}, {{ dropoffLatLng.lng.toFixed(5) }}
          </p>
          <p v-else class="text-[11px] text-slate-500">{{ t("ridePage.dropoffMapHint") }}</p>
        </section>

        <!-- ── Estimate ── -->
        <button
          type="button"
          class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold disabled:opacity-50"
          :disabled="!canEstimate || estimating"
          @click="getEstimate"
        >
          {{ estimating ? t('common.loading') : t('ridePage.estimateCta') }}
        </button>

        <!-- Estimate result -->
        <div
          v-if="estimate"
          class="ui-panel ui-reveal p-4 space-y-3 border-[var(--color-secondary)]/25 bg-[var(--color-secondary)]/5"
        >
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('ridePage.distanceLabel') }}</p>
              <p class="mt-0.5 text-lg font-bold tabular-nums text-slate-200">{{ estimate.distance_km }} km</p>
            </div>
            <div v-if="estimate.duration_min" class="text-center">
              <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('ridePage.durationLabel') }}</p>
              <p class="mt-0.5 text-lg font-bold tabular-nums text-slate-200">{{ t('ridePage.durationValue', { min: estimate.duration_min }) }}</p>
            </div>
            <div class="text-end">
              <p class="text-[10px] uppercase tracking-wider text-slate-500">{{ t('ridePage.fareLabel') }}</p>
              <p class="mt-0.5 text-lg font-bold tabular-nums text-[var(--color-secondary)]">{{ formatPrice(estimate.fare) }}</p>
            </div>
          </div>

          <!-- Payment toggle -->
          <div class="flex rounded-xl border border-slate-700/60 overflow-hidden text-sm font-semibold" role="group" :aria-label="`${t('ridePage.payWallet')} / ${t('ridePage.payCash')}`">
            <button
              type="button"
              class="flex-1 py-2.5 transition-colors"
              :class="paymentMethod === 'wallet' ? 'bg-[var(--color-secondary)] text-slate-950' : 'bg-slate-900/40 text-slate-400 hover:text-slate-200'"
              :disabled="walletInsufficient"
              @click="paymentMethod = 'wallet'"
            >
              {{ t('ridePage.walletShort') }}
            </button>
            <button
              type="button"
              class="flex-1 py-2.5 transition-colors"
              :class="paymentMethod === 'cash' ? 'bg-slate-200 text-slate-950' : 'bg-slate-900/40 text-slate-400 hover:text-slate-200'"
              @click="paymentMethod = 'cash'"
            >
              {{ t('ridePage.cashShort') }}
            </button>
          </div>

          <p
            v-if="walletInsufficient && paymentMethod === 'wallet'"
            role="alert"
            class="flex items-center gap-1.5 text-xs text-amber-300"
          >
            <AppIcon name="info" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {{ t('ridePage.insufficientWallet') }}
          </p>

          <!-- Request button -->
          <button
            type="button"
            class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold disabled:opacity-50"
            :disabled="requesting || (paymentMethod === 'wallet' && walletInsufficient)"
            @click="requestRide"
          >
            {{ requesting ? t('common.loading') : t('ridePage.requestCta') }}
          </button>
        </div>

        <!-- ══════════════════════════ PAST RIDES ══════════════════════════ -->
        <section v-if="rideHistory.length > 0 || historyLoading" class="space-y-2 pt-2">
          <p class="ui-kicker px-1">{{ t('ridePage.historyTitle') }}</p>

          <!-- Loading skeleton -->
          <template v-if="historyLoading && rideHistory.length === 0">
            <div
              v-for="n in 3"
              :key="n"
              class="h-14 w-full animate-pulse rounded-2xl bg-slate-800/60"
            />
          </template>

          <!-- History rows -->
          <ul v-else class="space-y-1.5">
            <li
              v-for="ride in rideHistory"
              :key="ride.id"
              class="ui-panel flex items-center gap-3 px-3 py-2.5"
            >
              <!-- Route: dropoff (primary) -->
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm text-slate-200">
                  {{ ride.dropoff_address || ride.pickup_address }}
                </p>
                <p class="mt-0.5 truncate text-[11px] text-slate-500">
                  {{ fmtDate(ride.created_at) }}
                </p>
              </div>

              <!-- Fare -->
              <span class="shrink-0 text-sm font-bold tabular-nums text-slate-200">
                {{ formatPrice(ride.fare) }}
              </span>

              <!-- Status chip -->
              <span
                class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                :class="ride.status === 'completed'
                  ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                  : 'border border-red-500/30 bg-red-500/10 text-red-300'"
              >
                {{ historyStatusLabel(ride.status) }}
              </span>

              <!-- Star rating (if rider rated the driver) -->
              <span
                v-if="ride.rider_driver_rating"
                class="shrink-0 flex items-center gap-0.5 text-amber-400"
                :aria-label="`${ride.rider_driver_rating} stars`"
              >
                <AppIcon name="star" class="h-3.5 w-3.5" aria-hidden="true" />
                <span class="text-[11px] font-semibold tabular-nums">{{ ride.rider_driver_rating }}</span>
              </span>
            </li>
          </ul>
        </section>

        <!-- Empty state — only show after load attempt with no results -->
        <p
          v-else-if="!historyLoading && rideHistory.length === 0 && customerStore.isAuthenticated"
          class="px-1 text-center text-xs text-slate-600"
        >
          {{ t('ridePage.historyEmpty') }}
        </p>
      </div>

    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useCustomerStore } from '../stores/customer';
import api from '../lib/api';
import { addTileLayer } from '../lib/mapTiles';
import AppIcon from '../components/AppIcon.vue';
import CustomerAuthModal from '../components/CustomerAuthModal.vue';

const { t, formatPrice, currentLocale } = useI18n();
const customerStore = useCustomerStore();

// ── Auth modal ────────────────────────────────────────────────────────────────
const showAuthModal = ref(false);

// ── Form state ────────────────────────────────────────────────────────────────
const pickupAddress  = ref('');
const dropoffAddress = ref('');
const pickupLatLng   = ref(null);  // { lat, lng }
const dropoffLatLng  = ref(null);
const locating       = ref(false);
const estimating     = ref(false);
const requesting     = ref(false);
const cancelling     = ref(false);
const estimate       = ref(null);  // { distance_km, fare }
const paymentMethod  = ref('wallet');
const errorMsg       = ref('');

// ── Rating state ──────────────────────────────────────────────────────────────
const ratingScore     = ref(0);
const submittingRating = ref(false);
const ratingDone      = ref(false);

// ── Cancelled state ───────────────────────────────────────────────────────────
const showCancelled   = ref(false);
const noDriverFound   = ref(false);  // system-cancelled (no driver accepted)

// ── Ride history ──────────────────────────────────────────────────────────────
const rideHistory    = ref([]);
const historyLoading = ref(false);

// ── Active ride polling ───────────────────────────────────────────────────────
const activeRide = ref(null);
let pollTimer = null;

const walletBalance = computed(() => {
  const raw = customerStore.customer?.wallet_balance;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
});

const walletInsufficient = computed(
  () => estimate.value != null && walletBalance.value < Number(estimate.value.fare),
);

const canEstimate = computed(
  () =>
    (pickupLatLng.value || pickupAddress.value.trim()) &&
    (dropoffLatLng.value || dropoffAddress.value.trim()),
);

const rideStatusLabel = computed(() => {
  switch (activeRide.value?.status) {
    case 'searching':   return t('ridePage.searching');
    case 'accepted':    return t('ridePage.driverAssigned');
    case 'arrived':     return t('ridePage.driverArrived');
    case 'in_progress': return t('ridePage.inProgress');
    case 'completed':   return t('ridePage.completed');
    case 'cancelled':   return t('ridePage.cancelled');
    default:            return '';
  }
});

const hasDriverPos = computed(
  () => activeRide.value?.driver?.driver_lat != null && activeRide.value?.driver?.driver_lng != null,
);

// ── Date helper ───────────────────────────────────────────────────────────────
const fmtDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString(currentLocale.value || undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return '';
  }
};

// ── Status label for history chips ────────────────────────────────────────────
const historyStatusLabel = (status) => {
  switch (status) {
    case 'completed': return t('ridePage.completed');
    case 'cancelled': return t('ridePage.cancelled');
    default:          return status;
  }
};

// ── Geolocation ───────────────────────────────────────────────────────────────
const useMyLocation = () => {
  if (!navigator.geolocation) {
    errorMsg.value = t('driver.geoUnavailable');
    return;
  }
  locating.value = true;
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      pickupLatLng.value = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      locating.value = false;
      // Centre pick-map on user position
      if (_pickMap) {
        _pickMap.setView([pos.coords.latitude, pos.coords.longitude], 14);
        ensurePickupMarker(pos.coords.latitude, pos.coords.longitude);
      }
    },
    () => {
      errorMsg.value = t('driver.locationDenied');
      locating.value = false;
    },
    { timeout: 8000 },
  );
};

// ── Estimate ──────────────────────────────────────────────────────────────────
const getEstimate = async () => {
  estimating.value = true;
  errorMsg.value = '';
  try {
    const payload = {
      pickup_lat:  pickupLatLng.value?.lat   ?? 0,
      pickup_lng:  pickupLatLng.value?.lng   ?? 0,
      dropoff_lat: dropoffLatLng.value?.lat  ?? 0,
      dropoff_lng: dropoffLatLng.value?.lng  ?? 0,
    };
    const res = await api.post('/rides/estimate/', payload);
    estimate.value = res.data;
    // Auto-switch to cash if wallet insufficient
    if (walletInsufficient.value) paymentMethod.value = 'cash';
  } catch {
    errorMsg.value = t('ridePage.errorEstimate');
  } finally {
    estimating.value = false;
  }
};

// ── Request ride ──────────────────────────────────────────────────────────────
const requestRide = async () => {
  requesting.value = true;
  errorMsg.value = '';
  try {
    const payload = {
      pickup_lat:       pickupLatLng.value?.lat   ?? 0,
      pickup_lng:       pickupLatLng.value?.lng   ?? 0,
      dropoff_lat:      dropoffLatLng.value?.lat  ?? 0,
      dropoff_lng:      dropoffLatLng.value?.lng  ?? 0,
      pickup_address:   pickupAddress.value.trim() || `${pickupLatLng.value?.lat}, ${pickupLatLng.value?.lng}`,
      dropoff_address:  dropoffAddress.value.trim() || `${dropoffLatLng.value?.lat}, ${dropoffLatLng.value?.lng}`,
      payment_method:   paymentMethod.value,
    };
    const res = await api.post('/rides/', payload);
    activeRide.value = res.data;
    startPolling();
  } catch (err) {
    const status = err?.response?.status;
    const code   = err?.response?.data?.code;
    if (status === 409) {
      errorMsg.value = t('ridePage.errorActive');
      // Try to load active ride
      fetchActiveRide();
    } else if (code === 'insufficient_wallet') {
      errorMsg.value = t('ridePage.insufficientWallet');
      paymentMethod.value = 'cash';
    } else {
      errorMsg.value = t('ridePage.errorRequest');
    }
  } finally {
    requesting.value = false;
  }
};

// ── Cancel ────────────────────────────────────────────────────────────────────
const cancelRide = async () => {
  if (!activeRide.value?.id) return;
  cancelling.value = true;
  try {
    await api.post(`/rides/${activeRide.value.id}/cancel/`);
    stopPolling();
    activeRide.value = null;
    showCancelled.value = true;
    fetchHistory();
  } catch {
    errorMsg.value = t('ridePage.errorRequest');
  } finally {
    cancelling.value = false;
  }
};

// ── Rating ────────────────────────────────────────────────────────────────────
const submitRating = async () => {
  if (!ratingScore.value || submittingRating.value || !activeRide.value?.id) return;
  submittingRating.value = true;
  try {
    await api.post(`/rides/${activeRide.value.id}/rate/`, { rating: ratingScore.value });
    ratingDone.value = true;
  } catch {
    // best-effort: leave form open
  } finally {
    submittingRating.value = false;
  }
};

// ── Reset to booking form ─────────────────────────────────────────────────────
const resetForm = () => {
  activeRide.value    = null;
  estimate.value      = null;
  ratingScore.value   = 0;
  ratingDone.value    = false;
  showCancelled.value = false;
  noDriverFound.value = false;
  errorMsg.value      = '';
  pickupAddress.value  = '';
  dropoffAddress.value = '';
  pickupLatLng.value   = null;
  dropoffLatLng.value  = null;
  destroyTrackingMap();
  fetchHistory();
};

// ── Polling ───────────────────────────────────────────────────────────────────
const fetchActiveRide = async () => {
  try {
    const res = await api.get('/rides/active/');
    if (res.data && res.data.id) {
      activeRide.value = res.data;
    }
  } catch {
    // 404 = no active ride, ignore
  }
};

const fetchHistory = async () => {
  historyLoading.value = true;
  try {
    const res = await api.get('/rides/history/');
    rideHistory.value = Array.isArray(res.data) ? res.data : [];
  } catch {
    // best-effort; leave existing history intact
  } finally {
    historyLoading.value = false;
  }
};

const startPolling = () => {
  stopPolling();
  pollTimer = setInterval(async () => {
    if (!activeRide.value?.id) { stopPolling(); return; }
    const prevStatus = activeRide.value.status;
    try {
      const res = await api.get('/rides/active/');
      if (res.data?.id) {
        activeRide.value = res.data;
        // Stop polling when terminal state
        if (['completed', 'cancelled'].includes(res.data.status)) {
          stopPolling();
          // System-cancelled: was searching/accepted, now cancelled (no user action)
          if (
            res.data.status === 'cancelled' &&
            ['searching', 'accepted', 'arrived'].includes(prevStatus) &&
            !cancelling.value
          ) {
            noDriverFound.value = true;
            activeRide.value = null;
            fetchHistory();
          } else if (res.data.status === 'completed') {
            fetchHistory();
          }
        }
      } else {
        // No active ride returned — likely completed/cancelled
        stopPolling();
      }
    } catch {
      // ignore transient errors
    }
  }, 5000);
};

const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
};

// ── Leaflet: pick-map (drop-off pin) ─────────────────────────────────────────
const pickMapEl      = ref(null);
const trackingMapEl  = ref(null);
let _leaflet         = null;
let _pickMap         = null;
let _pickupMarker    = null;
let _dropoffMarker   = null;
let _trackMap        = null;
let _trackDriverMkr  = null;

const ensureLeaflet = async () => {
  if (_leaflet) return _leaflet;
  const [{ default: L }, m2x, m, shadow] = await Promise.all([
    import('leaflet'),
    import('leaflet/dist/images/marker-icon-2x.png'),
    import('leaflet/dist/images/marker-icon.png'),
    import('leaflet/dist/images/marker-shadow.png'),
  ]);
  await import('leaflet/dist/leaflet.css');
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: m2x.default,
    iconUrl: m.default,
    shadowUrl: shadow.default,
  });
  _leaflet = L;
  return L;
};

const ensurePickupMarker = (lat, lng) => {
  if (!_pickMap || !_leaflet) return;
  const pos = [lat, lng];
  if (!_pickupMarker) {
    _pickupMarker = _leaflet.marker(pos, { opacity: 0.85 }).addTo(_pickMap);
  } else {
    _pickupMarker.setLatLng(pos);
  }
};

const initPickMap = async () => {
  if (!pickMapEl.value) return;
  const L = await ensureLeaflet();
  const defaultCenter = [33.5731, -7.5898]; // Casablanca fallback
  _pickMap = L.map(pickMapEl.value, { zoomControl: false, attributionControl: false }).setView(defaultCenter, 12);
  addTileLayer(L, _pickMap);

  // Tap to set drop-off
  _pickMap.on('click', (e) => {
    const { lat, lng } = e.latlng;
    dropoffLatLng.value = { lat, lng };
    if (!_dropoffMarker) {
      _dropoffMarker = L.marker([lat, lng]).addTo(_pickMap);
    } else {
      _dropoffMarker.setLatLng([lat, lng]);
    }
  });

  setTimeout(() => _pickMap && _pickMap.invalidateSize(), 0);
};

const destroyPickMap = () => {
  if (_pickMap) { _pickMap.remove(); _pickMap = null; _pickupMarker = null; _dropoffMarker = null; }
};

// ── Leaflet: tracking map ─────────────────────────────────────────────────────
const renderTrackingMap = async () => {
  const d = activeRide.value?.driver;
  if (!d || d.driver_lat == null || d.driver_lng == null || !trackingMapEl.value) return;
  const L = await ensureLeaflet();
  const driverPos = [Number(d.driver_lat), Number(d.driver_lng)];
  if (!_trackMap) {
    _trackMap = L.map(trackingMapEl.value, { zoomControl: false, attributionControl: false }).setView(driverPos, 14);
    addTileLayer(L, _trackMap);
  }
  if (!_trackDriverMkr) {
    _trackDriverMkr = L.marker(driverPos).addTo(_trackMap);
  } else {
    _trackDriverMkr.setLatLng(driverPos);
  }
  _trackMap.setView(driverPos, 14);
  setTimeout(() => _trackMap && _trackMap.invalidateSize(), 0);
};

const destroyTrackingMap = () => {
  if (_trackMap) { _trackMap.remove(); _trackMap = null; _trackDriverMkr = null; }
};

// Re-render tracking map when driver pos changes
watch(
  () => [activeRide.value?.driver?.driver_lat, activeRide.value?.driver?.driver_lng],
  () => { if (hasDriverPos.value) nextTick(renderTrackingMap); },
  { immediate: true },
);

// Re-init pick-map when the form section becomes visible
watch(
  () => customerStore.isAuthenticated,
  (auth) => { if (auth) nextTick(initPickMap); },
);

onMounted(async () => {
  // Check for in-progress ride immediately
  if (customerStore.isAuthenticated) {
    await fetchActiveRide();
    if (activeRide.value && !['completed', 'cancelled'].includes(activeRide.value.status)) {
      startPolling();
    }
    if (!activeRide.value) {
      nextTick(initPickMap);
    }
    fetchHistory();
  }
});

onBeforeUnmount(() => {
  stopPolling();
  destroyPickMap();
  destroyTrackingMap();
});
</script>
