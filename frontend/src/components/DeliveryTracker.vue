<template>
  <div v-if="delivery" class="rounded-2xl border border-slate-800 bg-slate-900 p-4 space-y-3">
    <div class="flex items-center justify-between">
      <h2 class="text-sm font-semibold text-slate-300">🛵 {{ t('deliveryTracker.title') }}</h2>
      <span
        class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
        :class="{
          'bg-amber-500/15 border border-amber-500/30 text-amber-300': delivery.status === 'searching',
          'bg-sky-500/15 border border-sky-500/30 text-sky-300': delivery.status === 'assigned' || delivery.status === 'at_restaurant',
          'bg-violet-500/15 border border-violet-500/30 text-violet-300': delivery.status === 'picked_up',
          'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300': delivery.status === 'delivered',
          'bg-red-500/15 border border-red-500/30 text-red-300': delivery.status === 'failed',
        }"
      >
        {{ statusLabel }}
      </span>
    </div>

    <!-- ETA (shown while the driver is on the way) -->
    <p v-if="etaMinutes" class="flex items-center gap-1.5 text-sm font-semibold text-emerald-300">
      🕐 {{ t('deliveryTracker.eta', { min: etaMinutes }) }}
    </p>

    <!-- Driver identity + contact -->
    <div v-if="delivery.driver" class="flex items-center gap-3">
      <div class="h-10 w-10 shrink-0 rounded-full bg-slate-700 flex items-center justify-center text-lg">🧑</div>
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-medium text-slate-200">{{ delivery.driver.name || t('deliveryTracker.driverUnnamed') }}</p>
        <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]">
          <span v-if="ratingText" class="text-amber-300">★ {{ ratingText }}</span>
          <span v-if="delivery.driver.vehicle" class="text-slate-400">{{ delivery.driver.vehicle }}</span>
          <span v-if="delivery.driver.is_online" class="text-emerald-400">{{ t('deliveryTracker.online') }}</span>
        </div>
      </div>
      <a
        v-if="delivery.driver.phone"
        :href="`tel:${delivery.driver.phone}`"
        class="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-sky-600/50 bg-sky-900/20 px-3 py-2 text-xs font-semibold text-sky-300 hover:bg-sky-900/35"
      >
        <AppIcon name="phone" class="h-4 w-4" />{{ t('deliveryTracker.call') }}
      </a>
    </div>
    <p v-else class="text-xs text-slate-400">{{ t('deliveryTracker.searching') }}</p>

    <!-- Addresses -->
    <div v-if="delivery.pickup_address || delivery.delivery_address" class="space-y-1 text-xs text-slate-400">
      <p v-if="delivery.pickup_address"><span class="text-slate-500">{{ t('deliveryTracker.from') }}:</span> {{ delivery.pickup_address }}</p>
      <p v-if="delivery.delivery_address"><span class="text-slate-500">{{ t('deliveryTracker.to') }}:</span> {{ delivery.delivery_address }}</p>
    </div>

    <!-- Live map: driver + destination -->
    <div v-show="hasDriverPos" ref="mapEl" class="h-48 w-full overflow-hidden rounded-xl border border-slate-800"></div>

    <!-- Position freshness — a frozen pin shouldn't look live -->
    <p v-if="hasDriverPos && positionAgeText" class="text-[11px]" :class="positionStale ? 'text-amber-400' : 'text-slate-500'">
      <span v-if="positionStale">⚠ </span>{{ positionAgeText }}
    </p>

    <!-- Maps link when driver position known -->
    <a
      v-if="hasDriverPos"
      :href="`https://www.google.com/maps/search/?api=1&query=${delivery.driver.lat},${delivery.driver.lng}`"
      target="_blank"
      rel="noopener noreferrer"
      class="inline-flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300"
    >
      📍 {{ t('deliveryTracker.viewMap') }}
    </a>

    <!-- Rate your driver (after delivery) -->
    <div v-if="showRating" class="border-t border-slate-800 pt-3 space-y-2">
      <p class="text-xs font-semibold text-slate-300">{{ t('deliveryTracker.rateDriver') }}</p>
      <div class="flex gap-1.5">
        <button
          v-for="n in 5"
          :key="n"
          type="button"
          class="text-2xl leading-none transition-transform hover:scale-110"
          :class="ratingScore >= n ? 'text-amber-400' : 'text-slate-600'"
          :aria-label="t('common.rateNStars', { n })"
          @click="ratingScore = n"
        >★</button>
      </div>
      <textarea
        v-model="ratingNote"
        rows="2"
        class="w-full resize-none rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-slate-500 focus:outline-none"
        :aria-label="t('deliveryTracker.ratingNote')"
        :placeholder="t('deliveryTracker.ratingNote')"
      />
      <button
        type="button"
        class="rounded-full bg-[var(--color-secondary,#f59e0b)] px-4 py-2 text-xs font-semibold text-slate-950 disabled:opacity-50"
        :disabled="!ratingScore || submittingRating"
        @click="submitRating"
      >
        {{ submittingRating ? '…' : t('deliveryTracker.submitRating') }}
      </button>
    </div>
    <p v-else-if="ratingDone" role="status" class="border-t border-slate-800 pt-3 text-center text-xs text-emerald-300">
      ✓ {{ t('deliveryTracker.ratingThanks') }}
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
let _map = null, _driverMarker = null, _destMarker = null, _leaflet = null;

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
  if (points.length > 1) _map.fitBounds(points, { padding: [30, 30], maxZoom: 15 });
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
  }
});
</script>
