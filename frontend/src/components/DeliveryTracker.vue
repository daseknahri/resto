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
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import AppIcon from './AppIcon.vue';

const props = defineProps({
  delivery: { type: Object, default: null },
});

const { t } = useI18n();

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
