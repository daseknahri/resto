<template>
  <div v-if="delivery" class="ui-panel ui-reveal space-y-3 p-4">
    <!-- Header: kicker + title + status pill -->
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="ui-kicker">{{ t('deliveryTracker.kicker') }}</p>
        <h2 class="ui-display flex items-center gap-1.5 text-sm font-semibold text-white">
          <AppIcon name="truck" class="h-4 w-4 shrink-0 text-[var(--color-secondary)]" aria-hidden="true" />
          {{ t('deliveryTracker.title') }}
        </h2>
      </div>
      <span
        class="ui-status-pill shrink-0"
        :class="{
          'border-amber-500/30 bg-amber-500/12 text-amber-300': delivery.status === 'searching',
          'border-sky-500/30 bg-sky-500/12 text-sky-300': delivery.status === 'assigned' || delivery.status === 'at_restaurant',
          'border-violet-500/30 bg-violet-500/12 text-violet-300': delivery.status === 'picked_up',
          'border-emerald-500/30 bg-emerald-500/12 text-emerald-300': delivery.status === 'delivered',
          'border-red-500/30 bg-red-500/12 text-red-300': delivery.status === 'failed',
        }"
        aria-live="polite"
        aria-atomic="true"
        :aria-label="t('deliveryTracker.statusAriaLabel', { status: statusLabel })"
      >
        {{ statusLabel }}
      </span>
    </div>

    <!-- ETA (shown while the driver is on the way) -->
    <p v-if="etaMinutes" class="flex items-center gap-1.5 text-sm font-semibold text-emerald-300" aria-live="polite" aria-atomic="true">
      <AppIcon name="info" class="h-4 w-4 shrink-0" aria-hidden="true" />
      {{ t('deliveryTracker.eta', { min: etaMinutes }) }}
    </p>

    <!-- Driver identity + contact -->
    <section v-if="delivery.driver" :aria-label="t('deliveryTracker.driverSection')" class="flex items-center gap-3">
      <div
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-800 text-slate-400"
        aria-hidden="true"
      >
        <AppIcon name="user" class="h-5 w-5" aria-hidden="true" />
      </div>
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-medium text-slate-200">
          {{ delivery.driver.name || t('deliveryTracker.driverUnnamed') }}
        </p>
        <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]">
          <span v-if="ratingText" class="inline-flex items-center gap-0.5 text-amber-300 tabular-nums">
            <AppIcon name="star" class="h-3 w-3 shrink-0" aria-hidden="true" />
            {{ ratingText }}
          </span>
          <span v-if="delivery.driver.vehicle" class="text-slate-400">{{ delivery.driver.vehicle }}</span>
          <span v-if="delivery.driver.is_online" class="inline-flex items-center gap-1 text-emerald-400">
            <span class="ui-live-dot bg-emerald-400" aria-hidden="true"></span>
            {{ t('deliveryTracker.online') }}
          </span>
        </div>
      </div>
      <a
        v-if="delivery.driver.phone"
        :href="`tel:${delivery.driver.phone}`"
        class="ui-btn-outline ui-touch-target ui-press shrink-0 gap-1.5 px-3 py-2 text-xs"
      >
        <AppIcon name="phone" class="h-4 w-4" aria-hidden="true" />
        {{ t('deliveryTracker.call') }}
      </a>
    </section>
    <p v-else class="ui-subtle text-xs">{{ t('deliveryTracker.searching') }}</p>

    <!-- Addresses -->
    <dl
      v-if="delivery.pickup_address || delivery.delivery_address"
      class="ui-admin-subcard space-y-1 px-3 py-2"
    >
      <div v-if="delivery.pickup_address" class="flex items-baseline gap-1.5 text-xs">
        <dt class="shrink-0 text-slate-500">{{ t('deliveryTracker.from') }}</dt>
        <dd class="min-w-0 truncate text-slate-300">{{ delivery.pickup_address }}</dd>
      </div>
      <div v-if="delivery.delivery_address" class="flex items-baseline gap-1.5 text-xs">
        <dt class="shrink-0 text-slate-500">{{ t('deliveryTracker.to') }}</dt>
        <dd class="min-w-0 truncate text-slate-300">{{ delivery.delivery_address }}</dd>
      </div>
    </dl>

    <!-- Live map: driver + destination -->
    <div
      v-show="hasDriverPos"
      ref="mapEl"
      class="h-48 w-full overflow-hidden rounded-xl border border-slate-800"
      role="img"
      :aria-label="t('deliveryTracker.mapAriaLabel')"
    ></div>

    <!-- Position freshness — a frozen pin shouldn't look live -->
    <p
      v-if="hasDriverPos && positionAgeText"
      class="flex items-center gap-1 text-[11px]"
      :class="positionStale ? 'text-amber-400' : 'text-slate-500'"
    >
      <AppIcon
        v-if="positionStale"
        name="info"
        class="h-3.5 w-3.5 shrink-0"
        aria-hidden="true"
      />
      {{ positionAgeText }}
    </p>

    <!-- Maps link when driver position known -->
    <a
      v-if="hasDriverPos"
      :href="`https://www.google.com/maps/search/?api=1&query=${delivery.driver.lat},${delivery.driver.lng}`"
      target="_blank"
      rel="noopener noreferrer"
      class="inline-flex items-center gap-1.5 rounded text-xs text-sky-400 transition-colors hover:text-sky-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/60"
    >
      <AppIcon name="location" class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      {{ t('deliveryTracker.viewMap') }}
      <span class="sr-only">{{ t('common.opensInNewTab') }}</span>
    </a>

    <!-- Rate your driver (after delivery) -->
    <div v-if="showRating" class="space-y-2 border-t border-slate-800 pt-3">
      <p class="ui-kicker mb-1">{{ t('deliveryTracker.rateKicker') }}</p>
      <p class="text-xs font-semibold text-slate-300">{{ t('deliveryTracker.rateDriver') }}</p>
      <div class="flex gap-1" role="radiogroup" :aria-label="t('deliveryTracker.rateDriver')">
        <button
          v-for="n in 5"
          :key="n"
          type="button"
          role="radio"
          class="ui-touch-target ui-press flex items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
          :class="ratingScore >= n ? 'text-amber-400' : 'text-slate-600 hover:text-slate-400'"
          :aria-label="t('common.rateNStars', { n })"
          :aria-checked="ratingScore === n"
          @click="ratingScore = n"
        >
          <AppIcon name="star" class="h-6 w-6" aria-hidden="true" />
        </button>
      </div>
      <label for="rating-note" class="text-[11px] text-slate-400">{{ t('deliveryTracker.ratingNote') }}</label>
      <textarea
        id="rating-note"
        v-model="ratingNote"
        rows="2"
        class="ui-textarea text-xs"
        :placeholder="t('deliveryTracker.ratingNote')"
      />
      <span id="rating-hint" class="sr-only">{{ t('deliveryTracker.ratingHint') }}</span>
      <button
        type="button"
        class="ui-btn-primary ui-press px-4 py-2 text-xs disabled:opacity-50"
        :disabled="!ratingScore || submittingRating"
        :aria-describedby="!ratingScore ? 'rating-hint' : undefined"
        @click="submitRating"
      >
        {{ submittingRating ? t('common.saving') : t('deliveryTracker.submitRating') }}
      </button>
    </div>
    <p
      v-else-if="ratingDone"
      role="status"
      class="flex items-center justify-center gap-1.5 border-t border-slate-800 pt-3 text-xs text-emerald-300"
    >
      <AppIcon name="check" class="h-4 w-4 shrink-0" aria-hidden="true" />
      {{ t('deliveryTracker.ratingThanks') }}
    </p>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import AppIcon from './AppIcon.vue';

const props = defineProps({
  delivery: { type: Object, default: null },
});

const { t } = useI18n();

// Straight-line km between two points (rough ETA only).
function haversineKm(lat1, lng1, lat2, lng2) {
  const toNum = (v) => (v === null || v === undefined || v === '' ? NaN : Number(v));
  const a1 = toNum(lat1), o1 = toNum(lng1), a2 = toNum(lat2), o2 = toNum(lng2);
  if (![a1, o1, a2, o2].every((n) => Number.isFinite(n))) return null;
  const R = 6371.0088;
  const rad = (d) => (d * Math.PI) / 180;
  const dLat = rad(a2 - a1), dLng = rad(o2 - o1);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a1)) * Math.cos(rad(a2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.asin(Math.min(1, Math.sqrt(s)));
}

// Rough ETA in minutes — only while the driver is en route to the customer.
// Straight-line distance ÷ ~22 km/h urban speed; clamped to a sane floor.
const etaMinutes = computed(() => {
  const d = props.delivery;
  if (!d || d.status !== 'picked_up') return null;
  // Prefer the server's route ETA (real road time when a routing engine is on);
  // fall back to the straight-line estimate.
  const serverEta = Number(d.eta_minutes);
  if (Number.isFinite(serverEta) && serverEta > 0) return Math.max(1, Math.round(serverEta));
  const km = haversineKm(d.driver?.lat, d.driver?.lng, d.delivery_lat, d.delivery_lng);
  if (km == null) return null;
  return Math.max(3, Math.round((km / 22) * 60));
});

const hasDriverPos = computed(
  () => props.delivery?.driver?.lat != null && props.delivery?.driver?.lng != null,
);

const statusLabel = computed(() => {
  const s = props.delivery?.status;
  return s ? t(`deliveryTracker.status_${s}`) : '';
});

const ratingText = computed(() => {
  const r = props.delivery?.driver?.rating;
  if (r == null) return '';
  const n = props.delivery?.driver?.rating_count || 0;
  return n > 0 ? `${r} (${n})` : `${r}`;
});

// Position freshness (recomputed each poll, when the parent passes a fresh delivery object).
const _positionMs = computed(() => {
  const ts = props.delivery?.driver?.position_updated_at;
  if (!ts) return null;
  const t = new Date(ts).getTime();
  return Number.isNaN(t) ? null : t;
});
const positionStale = computed(
  () => _positionMs.value != null && Date.now() - _positionMs.value > 3 * 60 * 1000,
);
const positionAgeText = computed(() => {
  if (_positionMs.value == null) return '';
  const mins = Math.max(0, Math.round((Date.now() - _positionMs.value) / 60000));
  return mins <= 0 ? t('deliveryTracker.updatedJustNow') : t('deliveryTracker.updatedAgo', { min: mins });
});

// ── Rate your driver (after delivery) ───────────────────────────────────────────
const ratingScore = ref(0);
const ratingNote = ref('');
const submittingRating = ref(false);
const justRated = ref(false);

const alreadyRated = computed(() => props.delivery?.ratings?.customer_driver_rating != null);
const ratingDone = computed(() => justRated.value || alreadyRated.value);
const showRating = computed(() => props.delivery?.status === 'delivered' && !ratingDone.value);

const submitRating = async () => {
  if (!ratingScore.value || submittingRating.value) return;
  const d = props.delivery;
  if (!d?.order_number || !d?.restaurant_slug) return;
  submittingRating.value = true;
  try {
    await api.post(
      `/marketplace/track/${d.order_number}/rate/`,
      { role: 'customer', score: ratingScore.value, note: ratingNote.value },
      { params: { restaurant: d.restaurant_slug } },
    );
    justRated.value = true;
  } catch {
    // best-effort; leave the form open so the customer can retry
  } finally {
    submittingRating.value = false;
  }
};

// ── Live driver map (Leaflet, lazy-loaded) ──────────────────────────────────────
const mapEl = ref(null);
let _map = null, _driverMarker = null, _destMarker = null, _routeLine = null, _leaflet = null;

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
  L.Icon.Default.mergeOptions({ iconRetinaUrl: m2x.default, iconUrl: m.default, shadowUrl: shadow.default });
  _leaflet = L;
  return L;
};

const renderMap = async () => {
  const d = props.delivery?.driver;
  if (!d || d.lat == null || d.lng == null || !mapEl.value) return;
  const L = await ensureLeaflet();
  const driverPos = [Number(d.lat), Number(d.lng)];
  if (!_map) {
    _map = L.map(mapEl.value, { zoomControl: false, attributionControl: false }).setView(driverPos, 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(_map);
  }
  if (!_driverMarker) _driverMarker = L.marker(driverPos).addTo(_map);
  else _driverMarker.setLatLng(driverPos);
  if (_driverMarker.bindPopup) _driverMarker.bindPopup(t('deliveryTracker.title'));

  const destLat = props.delivery?.delivery_lat, destLng = props.delivery?.delivery_lng;
  const points = [driverPos];
  if (destLat != null && destLng != null) {
    const destPos = [Number(destLat), Number(destLng)];
    if (!_destMarker) _destMarker = L.marker(destPos, { opacity: 0.7 }).addTo(_map);
    else _destMarker.setLatLng(destPos);
    points.push(destPos);
  }
  // Route line: the real street route from the server (OSRM) when present, else a
  // straight line driver → destination. This is the "short road to the point".
  const serverRoute = Array.isArray(props.delivery?.route) ? props.delivery.route : null;
  let linePts = null;
  if (serverRoute && serverRoute.length >= 2) {
    linePts = serverRoute
      .map((p) => [Number(p[0]), Number(p[1])])
      .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
  } else if (points.length > 1) {
    linePts = points;
  }
  if (linePts && linePts.length >= 2) {
    if (!_routeLine) _routeLine = L.polyline(linePts, { color: '#34d399', weight: 4, opacity: 0.75 }).addTo(_map);
    else _routeLine.setLatLngs(linePts);
  }
  const boundsPts = (linePts && linePts.length >= 2) ? linePts : points;
  if (boundsPts.length > 1) _map.fitBounds(boundsPts, { padding: [30, 30], maxZoom: 15 });
  else _map.setView(driverPos, 14);
  setTimeout(() => _map && _map.invalidateSize(), 0); // container just became visible
};

// Re-render whenever the driver position changes (poll-driven).
watch(
  () => [props.delivery?.driver?.lat, props.delivery?.driver?.lng],
  () => {
    if (hasDriverPos.value) nextTick(renderMap);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  if (_map) {
    _map.remove();
    _map = null;
    _driverMarker = null;
    _destMarker = null;
    _routeLine = null;
  }
});
</script>
