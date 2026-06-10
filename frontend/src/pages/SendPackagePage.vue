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
        <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_-10%,rgba(14,165,233,0.13),transparent_65%)]" />
        <div class="relative px-4 pb-10 pt-12 text-center space-y-5">
          <div class="mx-auto flex h-20 w-20 items-center justify-center rounded-[22px] border border-slate-700/60 bg-gradient-to-br from-slate-800/80 to-slate-900/80 shadow-xl">
            <AppIcon name="package" class="h-9 w-9 text-sky-400" aria-hidden="true" />
          </div>
          <div class="space-y-2">
            <p class="ui-kicker">{{ t('sendPackage.kicker') }}</p>
            <h1 class="ui-page-title">{{ t('sendPackage.title') }}</h1>
            <p class="ui-subtle mx-auto max-w-xs leading-relaxed">{{ t('sendPackage.signInFirst') }}</p>
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
        <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-sky-500/7 via-transparent to-transparent" />
        <div class="relative px-4">
          <p class="ui-kicker">{{ t('sendPackage.kicker') }}</p>
          <h1 class="ui-page-title flex items-center gap-2">
            <AppIcon name="package" class="h-5 w-5 text-sky-400" aria-hidden="true" />
            {{ t('sendPackage.title') }}
          </h1>
        </div>
      </header>

      <!-- ══════════════════════════ ACTIVE PACKAGE TRACKING ══════════════════════════ -->
      <div
        v-if="activePackage && activePackage.status !== 'completed' && activePackage.status !== 'cancelled'"
        class="px-3 pb-6 space-y-3"
        aria-live="polite"
        aria-atomic="false"
      >
        <!-- Status banner -->
        <div
          class="ui-panel ui-reveal relative overflow-hidden p-4 space-y-3"
          :class="{
            'border-amber-500/30 bg-amber-500/6': activePackage.status === 'searching',
            'border-sky-500/30 bg-sky-500/6': activePackage.status === 'accepted' || activePackage.status === 'arrived',
            'border-violet-500/30 bg-violet-500/6': activePackage.status === 'in_progress',
          }"
        >
          <!-- Pulse ring for active states -->
          <div
            class="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset motion-safe:animate-pulse"
            :class="{
              'ring-amber-500/15': activePackage.status === 'searching',
              'ring-sky-500/15': activePackage.status === 'accepted' || activePackage.status === 'arrived',
              'ring-violet-500/15': activePackage.status === 'in_progress',
            }"
            aria-hidden="true"
          />

          <!-- Status label -->
          <div class="relative flex items-center gap-3">
            <span
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border"
              :class="{
                'border-amber-500/40 bg-amber-500/12 text-amber-300': activePackage.status === 'searching',
                'border-sky-500/40 bg-sky-500/12 text-sky-300': activePackage.status === 'accepted' || activePackage.status === 'arrived',
                'border-violet-500/40 bg-violet-500/12 text-violet-300': activePackage.status === 'in_progress',
              }"
              aria-hidden="true"
            >
              <AppIcon name="package" class="h-4 w-4" aria-hidden="true" />
            </span>
            <div class="min-w-0 flex-1">
              <p
                class="text-sm font-semibold"
                :class="{
                  'text-amber-300': activePackage.status === 'searching',
                  'text-sky-300': activePackage.status === 'accepted' || activePackage.status === 'arrived',
                  'text-violet-300': activePackage.status === 'in_progress',
                }"
              >
                {{ packageStatusLabel }}
              </p>
              <p v-if="activePackage.driver" class="mt-0.5 text-xs text-slate-400">
                {{ activePackage.driver.name }}
                <span v-if="activePackage.driver.driver_vehicle" class="ms-1 text-slate-500">· {{ activePackage.driver.driver_vehicle }}</span>
              </p>
            </div>
            <!-- Phone link once driver assigned -->
            <a
              v-if="activePackage.driver?.phone"
              :href="`tel:${activePackage.driver.phone}`"
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
              <dd class="min-w-0 truncate text-slate-300">{{ activePackage.pickup_address }}</dd>
            </div>
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.dropoffLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activePackage.dropoff_address }}</dd>
            </div>
            <div v-if="activePackage.recipient_name" class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('sendPackage.recipientLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activePackage.recipient_name }}</dd>
            </div>
          </dl>
        </div>

        <!-- Live map (driver position) -->
        <div
          v-show="hasDriverPos"
          ref="trackingMapEl"
          class="h-52 w-full overflow-hidden rounded-2xl border border-slate-800"
          role="img"
          :aria-label="t('sendPackage.courierAssigned')"
        />

        <!-- Cancel button (searching / accepted) -->
        <button
          v-if="activePackage.status === 'searching' || activePackage.status === 'accepted'"
          type="button"
          class="w-full rounded-2xl border border-red-500/30 bg-red-500/8 py-3 text-sm font-semibold text-red-300 transition hover:bg-red-500/15 ui-press disabled:opacity-50"
          :disabled="cancelling"
          @click="cancelPackage"
        >
          {{ cancelling ? t('common.loading') : t('ridePage.cancelCta') }}
        </button>
      </div>

      <!-- ══════════════════════════ COMPLETED ══════════════════════════ -->
      <div
        v-else-if="activePackage && activePackage.status === 'completed'"
        class="px-3 pb-6 space-y-3"
      >
        <div class="ui-panel ui-reveal p-4 space-y-3 border-emerald-500/30 bg-emerald-500/6">
          <p class="ui-kicker">{{ t('sendPackage.delivered') }}</p>
          <dl class="space-y-1">
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.pickupLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activePackage.pickup_address }}</dd>
            </div>
            <div class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('ridePage.dropoffLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activePackage.dropoff_address }}</dd>
            </div>
            <div v-if="activePackage.recipient_name" class="flex items-baseline gap-1.5 text-xs">
              <dt class="shrink-0 text-slate-500">{{ t('sendPackage.recipientLabel') }}</dt>
              <dd class="min-w-0 truncate text-slate-300">{{ activePackage.recipient_name }}</dd>
            </div>
          </dl>
        </div>

        <!-- Send another -->
        <button
          type="button"
          class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold"
          @click="resetForm"
        >
          {{ t('sendPackage.title') }}
        </button>
      </div>

      <!-- ══════════════════════════ CANCELLED ══════════════════════════ -->
      <div
        v-else-if="showCancelled"
        class="px-3 pb-6 space-y-3"
      >
        <div class="ui-panel ui-reveal p-4 border-red-500/25 bg-red-500/6 space-y-3">
          <p class="text-sm font-semibold text-red-300">{{ t('sendPackage.cancelled') }}</p>
        </div>
        <button
          type="button"
          class="ui-btn-primary ui-press w-full py-3 text-sm font-semibold"
          @click="resetForm"
        >
          {{ t('sendPackage.title') }}
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
          <p class="flex-1 text-sm text-amber-200">{{ t('sendPackage.noCourierFound') }}</p>
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
            <AppIcon name="location" class="h-3.5 w-3.5 text-sky-400" aria-hidden="true" />
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
          <p v-if="dropoffLatLng" class="text-[11px] text-sky-300 flex items-center gap-1">
            <AppIcon name="check" class="h-3 w-3" aria-hidden="true" />
            {{ dropoffLatLng.lat.toFixed(5) }}, {{ dropoffLatLng.lng.toFixed(5) }}
          </p>
          <p v-else class="text-[11px] text-slate-500">{{ t("ridePage.dropoffMapHint") }}</p>
        </section>

        <!-- ── Recipient details ── -->
        <section class="ui-panel ui-reveal p-4 space-y-3">
          <p class="ui-kicker flex items-center gap-1.5">
            <AppIcon name="user" class="h-3.5 w-3.5 text-sky-400" aria-hidden="true" />
            {{ t('sendPackage.recipientLabel') }}
          </p>
          <input
            v-model="recipientName"
            type="text"
            class="ui-input w-full"
            :placeholder="t('sendPackage.recipientNamePlaceholder')"
            :aria-label="t('sendPackage.recipientNamePlaceholder')"
            required
          />
          <input
            v-model="recipientPhone"
            type="tel"
            class="ui-input w-full"
            :placeholder="t('sendPackage.recipientPhonePlaceholder')"
            :aria-label="t('sendPackage.recipientPhonePlaceholder')"
            required
          />
          <textarea
            v-model="packageNote"
            class="ui-input w-full resize-none"
            rows="2"
            :placeholder="t('sendPackage.packageNotePlaceholder')"
            :aria-label="t('sendPackage.packageNotePlaceholder')"
          />
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
          class="ui-panel ui-reveal p-4 space-y-3 border-sky-500/25 bg-sky-500/5"
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
              <p class="mt-0.5 text-lg font-bold tabular-nums text-sky-400">{{ formatPrice(estimate.fare) }}</p>
            </div>
          </div>

          <!-- Payment toggle -->
          <div class="flex rounded-xl border border-slate-700/60 overflow-hidden text-sm font-semibold" role="group" :aria-label="`${t('ridePage.payWallet')} / ${t('ridePage.payCash')}`">
            <button
              type="button"
              class="flex-1 py-2.5 transition-colors"
              :class="paymentMethod === 'wallet' ? 'bg-sky-500 text-slate-950' : 'bg-slate-900/40 text-slate-400 hover:text-slate-200'"
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
            :disabled="requesting || (paymentMethod === 'wallet' && walletInsufficient) || !canRequest"
            @click="requestPackage"
          >
            {{ requesting ? t('common.loading') : t('sendPackage.requestCta') }}
          </button>
        </div>

        <!-- ══════════════════════════ PACKAGE HISTORY ══════════════════════════ -->
        <section v-if="packageHistory.length > 0 || historyLoading" class="space-y-2 pt-2">
          <p class="ui-kicker px-1">{{ t('sendPackage.historyTitle') }}</p>

          <!-- Loading skeleton -->
          <template v-if="historyLoading && packageHistory.length === 0">
            <div
              v-for="n in 3"
              :key="n"
              class="h-14 w-full animate-pulse rounded-2xl bg-slate-800/60"
            />
          </template>

          <!-- History rows -->
          <ul v-else class="space-y-1.5">
            <li
              v-for="pkg in packageHistory"
              :key="pkg.id"
              class="ui-panel flex items-center gap-3 px-3 py-2.5"
            >
              <!-- Route: dropoff (primary) -->
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm text-slate-200">
                  {{ pkg.recipient_name || pkg.dropoff_address || pkg.pickup_address }}
                </p>
                <p class="mt-0.5 truncate text-[11px] text-slate-500">
                  {{ fmtDate(pkg.created_at) }}
                </p>
              </div>

              <!-- Fare -->
              <span class="shrink-0 text-sm font-bold tabular-nums text-slate-200">
                {{ formatPrice(pkg.fare) }}
              </span>

              <!-- Status chip -->
              <span
                class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                :class="pkg.status === 'completed'
                  ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                  : 'border border-red-500/30 bg-red-500/10 text-red-300'"
              >
                {{ historyStatusLabel(pkg.status) }}
              </span>
            </li>
          </ul>
        </section>

        <!-- Empty state — only show after load attempt with no results -->
        <p
          v-else-if="!historyLoading && packageHistory.length === 0 && customerStore.isAuthenticated"
          class="px-1 text-center text-xs text-slate-600"
        >
          {{ t('sendPackage.historyEmpty') }}
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
const recipientName  = ref('');
const recipientPhone = ref('');
const packageNote    = ref('');
const locating       = ref(false);
const estimating     = ref(false);
const requesting     = ref(false);
const cancelling     = ref(false);
const estimate       = ref(null);  // { distance_km, fare }
const paymentMethod  = ref('wallet');
const errorMsg       = ref('');

// ── Cancelled state ───────────────────────────────────────────────────────────
const showCancelled = ref(false);
const noDriverFound = ref(false);  // system-cancelled (no courier accepted)

// ── Package history ───────────────────────────────────────────────────────────
const allHistory     = ref([]);
const historyLoading = ref(false);

// ── Active package polling ────────────────────────────────────────────────────
// Holds the active trip only if kind === 'package'; ride trips are ignored here.
const activePackage = ref(null);
let pollTimer = null;

// ── Derived ───────────────────────────────────────────────────────────────────
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

const canRequest = computed(
  () => recipientName.value.trim() !== '' && recipientPhone.value.trim() !== '',
);

// Package history is a client-side filter of all history items with kind === 'package'
const packageHistory = computed(
  () => allHistory.value.filter((r) => r.kind === 'package'),
);

const packageStatusLabel = computed(() => {
  switch (activePackage.value?.status) {
    case 'searching':   return t('sendPackage.searching');
    case 'accepted':    return t('sendPackage.courierAssigned');
    case 'arrived':     return t('sendPackage.pickedUp');
    case 'in_progress': return t('sendPackage.pickedUp');
    case 'completed':   return t('sendPackage.delivered');
    case 'cancelled':   return t('sendPackage.cancelled');
    default:            return '';
  }
});

const hasDriverPos = computed(
  () => activePackage.value?.driver?.driver_lat != null && activePackage.value?.driver?.driver_lng != null,
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
    case 'completed': return t('sendPackage.delivered');
    case 'cancelled': return t('sendPackage.cancelled');
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
    if (walletInsufficient.value) paymentMethod.value = 'cash';
  } catch {
    errorMsg.value = t('ridePage.errorEstimate');
  } finally {
    estimating.value = false;
  }
};

// ── Request package ───────────────────────────────────────────────────────────
const requestPackage = async () => {
  if (!canRequest.value) {
    errorMsg.value = t('sendPackage.recipientRequired');
    return;
  }
  requesting.value = true;
  errorMsg.value = '';
  try {
    const payload = {
      kind:             'package',
      pickup_lat:       pickupLatLng.value?.lat   ?? 0,
      pickup_lng:       pickupLatLng.value?.lng   ?? 0,
      dropoff_lat:      dropoffLatLng.value?.lat  ?? 0,
      dropoff_lng:      dropoffLatLng.value?.lng  ?? 0,
      pickup_address:   pickupAddress.value.trim() || `${pickupLatLng.value?.lat}, ${pickupLatLng.value?.lng}`,
      dropoff_address:  dropoffAddress.value.trim() || `${dropoffLatLng.value?.lat}, ${dropoffLatLng.value?.lng}`,
      payment_method:   paymentMethod.value,
      recipient_name:   recipientName.value.trim(),
      recipient_phone:  recipientPhone.value.trim(),
      package_note:     packageNote.value.trim(),
    };
    const res = await api.post('/rides/', payload);
    activePackage.value = res.data;
    startPolling();
  } catch (err) {
    const status = err?.response?.status;
    const code   = err?.response?.data?.code;
    if (status === 409) {
      errorMsg.value = t('ridePage.errorActive');
      // Fetch active ride — if it's a package, show it; if it's a ride, just show error
      fetchActiveTrip();
    } else if (code === 'insufficient_wallet') {
      errorMsg.value = t('ridePage.insufficientWallet');
      paymentMethod.value = 'cash';
    } else if (code === 'missing_field') {
      errorMsg.value = t('sendPackage.recipientRequired');
    } else {
      errorMsg.value = t('ridePage.errorRequest');
    }
  } finally {
    requesting.value = false;
  }
};

// ── Cancel ────────────────────────────────────────────────────────────────────
const cancelPackage = async () => {
  if (!activePackage.value?.id) return;
  cancelling.value = true;
  try {
    await api.post(`/rides/${activePackage.value.id}/cancel/`);
    stopPolling();
    activePackage.value = null;
    showCancelled.value = true;
    fetchHistory();
  } catch {
    errorMsg.value = t('ridePage.errorRequest');
  } finally {
    cancelling.value = false;
  }
};

// ── Reset to booking form ─────────────────────────────────────────────────────
const resetForm = () => {
  activePackage.value  = null;
  estimate.value       = null;
  showCancelled.value  = false;
  noDriverFound.value  = false;
  errorMsg.value       = '';
  pickupAddress.value  = '';
  dropoffAddress.value = '';
  pickupLatLng.value   = null;
  dropoffLatLng.value  = null;
  recipientName.value  = '';
  recipientPhone.value = '';
  packageNote.value    = '';
  destroyTrackingMap();
  fetchHistory();
};

// ── Polling ───────────────────────────────────────────────────────────────────
const fetchActiveTrip = async () => {
  try {
    const res = await api.get('/rides/active/');
    if (res.data && res.data.id) {
      // Only claim as activePackage if kind === 'package'
      if (res.data.kind === 'package') {
        activePackage.value = res.data;
      }
      // If kind === 'ride', ignore — the 409 error message is already shown
    }
  } catch {
    // 404 = no active ride, ignore
  }
};

const fetchHistory = async () => {
  historyLoading.value = true;
  try {
    const res = await api.get('/rides/history/');
    allHistory.value = Array.isArray(res.data) ? res.data : [];
  } catch {
    // best-effort; leave existing history intact
  } finally {
    historyLoading.value = false;
  }
};

const startPolling = () => {
  stopPolling();
  pollTimer = setInterval(async () => {
    if (!activePackage.value?.id) { stopPolling(); return; }
    const prevStatus = activePackage.value.status;
    try {
      const res = await api.get('/rides/active/');
      if (res.data?.id && res.data.kind === 'package') {
        activePackage.value = res.data;
        if (['completed', 'cancelled'].includes(res.data.status)) {
          stopPolling();
          if (
            res.data.status === 'cancelled' &&
            ['searching', 'accepted', 'arrived'].includes(prevStatus) &&
            !cancelling.value
          ) {
            noDriverFound.value = true;
            activePackage.value = null;
            fetchHistory();
          } else if (res.data.status === 'completed') {
            fetchHistory();
          }
        }
      } else {
        // Active trip is gone or switched to a ride kind — stop
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
const pickMapEl     = ref(null);
const trackingMapEl = ref(null);
let _leaflet        = null;
let _pickMap        = null;
let _pickupMarker   = null;
let _dropoffMarker  = null;
let _trackMap       = null;
let _trackDriverMkr = null;

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
  const d = activePackage.value?.driver;
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
  () => [activePackage.value?.driver?.driver_lat, activePackage.value?.driver?.driver_lng],
  () => { if (hasDriverPos.value) nextTick(renderTrackingMap); },
  { immediate: true },
);

// Re-init pick-map when the form section becomes visible
watch(
  () => customerStore.isAuthenticated,
  (auth) => { if (auth) nextTick(initPickMap); },
);

onMounted(async () => {
  if (customerStore.isAuthenticated) {
    await fetchActiveTrip();
    if (activePackage.value && !['completed', 'cancelled'].includes(activePackage.value.status)) {
      startPolling();
    }
    if (!activePackage.value) {
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
