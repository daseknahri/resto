<template>
  <main class="min-h-screen bg-slate-950 px-4 py-6">
    <div class="mx-auto max-w-md">
      <h1 class="text-xl font-bold text-slate-100">{{ t('recipientTrack.title') }}</h1>

      <!-- Loading -->
      <p v-if="loading" class="mt-6 text-sm text-slate-500">{{ t('recipientTrack.loading') }}</p>

      <!-- Not found / expired -->
      <div
        v-else-if="notFound"
        class="mt-6 rounded-xl border border-slate-700/60 bg-slate-900/60 p-4 text-sm text-slate-400"
      >
        {{ t('recipientTrack.notFound') }}
      </div>

      <template v-else-if="track">
        <p class="mt-1 text-sm text-slate-400">
          {{ introText }}
        </p>

        <!-- Status banner -->
        <div
          class="mt-4 rounded-xl px-4 py-3 text-sm font-semibold"
          :class="bannerClass"
        >
          {{ statusLabel }}
          <span v-if="track.eta_minutes && isLive" class="block text-xs font-normal opacity-90">
            {{ t('recipientTrack.etaMinutes', { n: track.eta_minutes }) }}
          </span>
        </div>

        <!-- Courier card -->
        <div
          v-if="track.courier"
          class="mt-4 flex items-center gap-3 rounded-xl border border-slate-700/60 bg-slate-900/60 p-3"
        >
          <div
            class="flex h-10 w-10 items-center justify-center rounded-full border border-sky-500/40 bg-sky-500/12 font-bold text-sky-300"
          >
            {{ courierInitial }}
          </div>
          <div>
            <p class="text-xs uppercase tracking-wide text-slate-500">{{ t('recipientTrack.courierLabel') }}</p>
            <p class="text-sm font-semibold text-slate-100">{{ track.courier.first_name || '—' }}</p>
            <p v-if="track.courier.vehicle" class="text-xs text-slate-400">
              {{ t('recipientTrack.vehicleLabel') }}: {{ track.courier.vehicle }}
            </p>
          </div>
        </div>

        <!-- Handover code -->
        <div
          v-if="track.delivery_code"
          class="mt-4 rounded-xl border border-sky-500/30 bg-sky-500/6 p-4 text-center"
        >
          <p class="text-xs font-semibold uppercase tracking-wider text-sky-400">
            {{ t('recipientTrack.codeTitle') }}
          </p>
          <p class="mt-1 tabular-nums text-3xl font-bold tracking-[0.3em] text-white">
            {{ track.delivery_code }}
          </p>
          <p class="mt-1 text-xs text-sky-300">{{ t('recipientTrack.codeHint') }}</p>
        </div>

        <!-- Live map -->
        <div v-if="hasDriverPos" class="mt-4">
          <p class="mb-1 text-xs uppercase tracking-wide text-slate-500">{{ t('recipientTrack.liveMap') }}</p>
          <div ref="trackingMapEl" class="h-56 w-full overflow-hidden rounded-xl border border-slate-800"></div>
        </div>

        <!-- Addresses -->
        <dl class="mt-4 space-y-2 text-sm">
          <div v-if="track.pickup_address">
            <dt class="text-xs uppercase tracking-wide text-slate-500">{{ t('recipientTrack.fromLabel') }}</dt>
            <dd class="text-slate-300">{{ track.pickup_address }}</dd>
          </div>
          <div v-if="track.dropoff_address">
            <dt class="text-xs uppercase tracking-wide text-slate-500">{{ t('recipientTrack.toLabel') }}</dt>
            <dd class="text-slate-300">{{ track.dropoff_address }}</dd>
          </div>
        </dl>
      </template>
    </div>
  </main>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import { addTileLayer } from '../lib/mapTiles';

const { t } = useI18n();
const route = useRoute();
const token = route.params.token;

const track = ref(null);
const loading = ref(true);
const notFound = ref(false);
let pollTimer = null;

const TERMINAL = ['completed', 'cancelled'];
const isLive = computed(() => track.value && !TERMINAL.includes(track.value.status));

const introText = computed(() => {
  if (!track.value) return '';
  return track.value.recipient_name
    ? t('recipientTrack.intro', { name: track.value.recipient_name })
    : t('recipientTrack.introNoName');
});

const statusLabel = computed(() => {
  const s = track.value?.status;
  const map = {
    searching: 'recipientTrack.statusSearching',
    accepted: 'recipientTrack.statusAccepted',
    arrived: 'recipientTrack.statusArrived',
    in_progress: 'recipientTrack.statusInProgress',
    completed: 'recipientTrack.statusCompleted',
    cancelled: 'recipientTrack.statusCancelled',
    // scheduled trips display as "finding a courier" to the recipient
    scheduled: 'recipientTrack.statusSearching',
  };
  return t(map[s] || 'recipientTrack.statusSearching');
});

const bannerClass = computed(() => {
  const s = track.value?.status;
  if (s === 'completed') return 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
  if (s === 'cancelled') return 'border border-rose-500/30 bg-rose-500/10 text-rose-300';
  if (s === 'in_progress') return 'border border-violet-500/30 bg-violet-500/10 text-violet-300';
  return 'border border-sky-500/30 bg-sky-500/8 text-sky-300';
});

const courierInitial = computed(() => {
  const n = track.value?.courier?.first_name || '';
  return n ? n.charAt(0).toUpperCase() : '?';
});

const hasDriverPos = computed(
  () => track.value && track.value.driver_lat != null && track.value.driver_lng != null,
);

const fetchTrack = async () => {
  try {
    const res = await api.get(`/track/${encodeURIComponent(token)}/`);
    track.value = res.data;
    notFound.value = false;
  } catch (e) {
    if (e?.response?.status === 404) {
      notFound.value = true;
      track.value = null;
      stopPolling();
    }
    // transient (5xx/network): keep the last good state, let polling retry
  } finally {
    loading.value = false;
  }
};

const startPolling = () => {
  stopPolling();
  pollTimer = setInterval(async () => {
    if (notFound.value) { stopPolling(); return; }
    await fetchTrack();
    if (track.value && TERMINAL.includes(track.value.status)) stopPolling();
  }, 8000);
};

const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
};

// ── Leaflet live map (read-only courier marker) ──────────────────────────────
const trackingMapEl = ref(null);
let _leaflet = null;
let _trackMap = null;
let _trackMkr = null;

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

const renderTrackingMap = async () => {
  if (!hasDriverPos.value || !trackingMapEl.value) return;
  const L = await ensureLeaflet();
  const pos = [Number(track.value.driver_lat), Number(track.value.driver_lng)];
  if (!_trackMap) {
    _trackMap = L.map(trackingMapEl.value, { zoomControl: false, attributionControl: false }).setView(pos, 14);
    addTileLayer(L, _trackMap);
  }
  if (!_trackMkr) {
    _trackMkr = L.marker(pos).addTo(_trackMap);
  } else {
    _trackMkr.setLatLng(pos);
  }
  _trackMap.setView(pos, 14);
  setTimeout(() => _trackMap && _trackMap.invalidateSize(), 0);
};

const destroyTrackingMap = () => {
  if (_trackMap) { _trackMap.remove(); _trackMap = null; _trackMkr = null; }
};

watch(
  () => [track.value?.driver_lat, track.value?.driver_lng],
  () => { if (hasDriverPos.value) nextTick(renderTrackingMap); },
);

onMounted(async () => {
  await fetchTrack();
  if (track.value && hasDriverPos.value) nextTick(renderTrackingMap);
  if (track.value && !TERMINAL.includes(track.value.status)) startPolling();
});

onBeforeUnmount(() => {
  stopPolling();
  destroyTrackingMap();
});
</script>
