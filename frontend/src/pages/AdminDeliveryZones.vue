<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-white">{{ t('adminZones.title') }}</h1>
        <p class="text-sm text-slate-400 mt-0.5">{{ t('adminZones.subtitle') }}</p>
      </div>
      <button
        class="rounded-full bg-[var(--color-secondary,#f59e0b)] px-4 py-2 text-xs font-semibold text-slate-950 hover:opacity-90"
        @click="openCreate"
      >
        + {{ t('adminZones.newZone') }}
      </button>
    </div>

    <!-- Loading: skeleton table -->
    <div v-if="loading" class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th class="px-4 py-3 text-left">#</th>
            <th class="px-4 py-3 text-left">{{ t('adminZones.colName') }}</th>
            <th class="px-4 py-3 text-left">{{ t('adminZones.colCity') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminZones.colRadius') }}</th>
            <th class="px-4 py-3 text-center">{{ t('adminZones.colPolygon') }}</th>
            <th class="px-4 py-3 text-center">{{ t('adminZones.colStatus') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminZones.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="i in 4" :key="i" class="animate-pulse">
            <td class="px-4 py-3"><div class="h-3 w-4 rounded bg-slate-700/60" /></td>
            <td class="px-4 py-3"><div class="h-3 w-28 rounded bg-slate-700/60" /></td>
            <td class="px-4 py-3"><div class="h-3 w-20 rounded bg-slate-800/60" /></td>
            <td class="px-4 py-3"><div class="ml-auto h-3 w-10 rounded bg-slate-800/50" /></td>
            <td class="px-4 py-3"><div class="mx-auto h-3 w-10 rounded bg-slate-800/50" /></td>
            <td class="px-4 py-3"><div class="mx-auto h-4 w-14 rounded-full bg-slate-800/50" /></td>
            <td class="px-4 py-3"><div class="ml-auto h-3 w-16 rounded bg-slate-800/40" /></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Error -->
    <div v-else-if="fetchError" class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3">
      <svg viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('adminZones.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchZones"
      >{{ t('common.retry') }}</button>
    </div>

    <div v-else-if="!zones.length" class="py-12 text-center text-sm text-slate-400">{{ t('adminZones.empty') }}</div>

    <!-- Zones table -->
    <div v-else class="overflow-x-auto rounded-2xl border border-slate-700/60">
      <table class="w-full text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th class="px-4 py-3 text-left">#</th>
            <th class="px-4 py-3 text-left">{{ t('adminZones.colName') }}</th>
            <th class="px-4 py-3 text-left">{{ t('adminZones.colCity') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminZones.colRadius') }}</th>
            <th class="px-4 py-3 text-center">{{ t('adminZones.colPolygon') }}</th>
            <th class="px-4 py-3 text-center">{{ t('adminZones.colStatus') }}</th>
            <th class="px-4 py-3 text-right">{{ t('adminZones.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="zone in zones" :key="zone.id" class="hover:bg-slate-800/30 transition-colors">
            <td class="px-4 py-3 text-slate-500 text-xs">{{ zone.id }}</td>
            <td class="px-4 py-3 text-slate-200 font-medium">{{ zone.name }}</td>
            <td class="px-4 py-3 text-slate-400">{{ zone.city }}</td>
            <td class="px-4 py-3 text-right text-slate-400">{{ zone.approx_radius_km }} km</td>
            <td class="px-4 py-3 text-center text-slate-400 text-xs">{{ t('adminZones.polygonPts', { count: zone.polygon.length }) }}</td>
            <td class="px-4 py-3 text-center">
              <span
                class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="zone.is_active
                  ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                  : 'bg-slate-700/50 border border-slate-600 text-slate-400'"
              >
                {{ zone.is_active ? t('adminZones.active') : t('adminZones.inactive') }}
              </span>
            </td>
            <td class="px-4 py-3 text-right">
              <div class="flex justify-end items-center gap-2">
                <button
                  class="text-xs text-sky-400 hover:text-sky-300"
                  @click="openEdit(zone)"
                >{{ t('adminZones.edit') }}</button>
                <template v-if="confirmDeleteId === zone.id">
                  <span class="text-[11px] text-red-300">{{ zone.name }}?</span>
                  <button
                    class="text-[11px] font-semibold text-red-400 hover:text-red-300 disabled:opacity-50"
                    :disabled="deletingId === zone.id"
                    @click="deleteZone(zone)"
                  >{{ deletingId === zone.id ? '…' : t('common.confirm') }}</button>
                  <button class="text-[11px] text-slate-500 hover:text-slate-300" @click="confirmDeleteId = null">{{ t('common.cancel') }}</button>
                </template>
                <button
                  v-else
                  class="text-xs text-red-400 hover:text-red-300"
                  @click="confirmDeleteId = zone.id"
                >{{ t('adminZones.delete') }}</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Zone form drawer -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-all duration-200"
        enter-from-class="opacity-0 translate-y-4"
        leave-active-class="transition-all duration-150"
        leave-to-class="opacity-0 translate-y-4"
      >
        <div
          v-if="showForm"
          class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/60"
          @click.self="closeForm"
          @keydown.esc.window="closeForm"
        >
          <div role="dialog" aria-modal="true" class="w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-700 p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 class="text-base font-bold text-white">
              {{ editing ? t('adminZones.editTitle') : t('adminZones.createTitle') }}
            </h2>

            <div class="space-y-3">
              <!-- Name -->
              <div>
                <label class="block text-xs text-slate-400 mb-1">
                  {{ t('adminZones.fieldName') }}
                  <input v-model="form.name" type="text" class="admin-input" :placeholder="t('adminZones.namePlaceholder')" />
                </label>
              </div>
              <!-- City -->
              <div>
                <label class="block text-xs text-slate-400 mb-1">
                  {{ t('adminZones.fieldCity') }}
                  <input v-model="form.city" type="text" class="admin-input" :placeholder="t('adminZones.cityPlaceholder')" />
                </label>
              </div>
              <!-- Centre coordinates -->
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs text-slate-400 mb-1">
                    {{ t('adminZones.fieldCenterLat') }}
                    <input v-model.number="form.center_lat" type="number" step="0.0001" class="admin-input" placeholder="48.8566" />
                  </label>
                </div>
                <div>
                  <label class="block text-xs text-slate-400 mb-1">
                    {{ t('adminZones.fieldCenterLng') }}
                    <input v-model.number="form.center_lng" type="number" step="0.0001" class="admin-input" placeholder="2.3522" />
                  </label>
                </div>
              </div>
              <!-- Approx radius -->
              <div>
                <label class="block text-xs text-slate-400 mb-1">
                  {{ t('adminZones.fieldRadius') }}
                  <input v-model.number="form.approx_radius_km" type="number" step="0.5" min="0.5" class="admin-input" placeholder="5" />
                </label>
              </div>
              <!-- Polygon JSON -->
              <div>
                <label class="block text-xs text-slate-400 mb-1">
                  {{ t('adminZones.fieldPolygon') }}
                  <span class="text-slate-600"> — JSON array of &#123;lat, lng&#125;</span>
                  <textarea
                    v-model="polygonJson"
                    rows="5"
                    class="admin-input font-mono text-[11px] resize-y"
                    :placeholder='`[{"lat":48.86,"lng":2.34},{"lat":48.87,"lng":2.35},{"lat":48.85,"lng":2.36}]`'
                  />
                </label>
                <p v-if="polygonError" class="text-xs text-red-400 mt-1">{{ polygonError }}</p>
              </div>
              <!-- Fee tiers JSON -->
              <div>
                <label class="block text-xs text-slate-400 mb-1">
                  {{ t('adminZones.fieldFeeTiers') }}
                  <span class="text-slate-600"> — JSON array of &#123;km_up_to, fee&#125;</span>
                  <textarea
                    v-model="feeTiersJson"
                    rows="3"
                    class="admin-input font-mono text-[11px] resize-y"
                    :placeholder='`[{"km_up_to":3,"fee":2.5},{"km_up_to":null,"fee":5.0}]`'
                  />
                </label>
                <p v-if="feeTiersError" class="text-xs text-red-400 mt-1">{{ feeTiersError }}</p>
                <p class="text-[10px] text-slate-600 mt-0.5">{{ t('adminZones.feeTiersHint') }}</p>
              </div>
              <!-- Active -->
              <label class="flex items-center gap-2 cursor-pointer">
                <input v-model="form.is_active" type="checkbox" class="accent-[var(--color-secondary,#f59e0b)]" />
                <span class="text-sm text-slate-300">{{ t('adminZones.fieldActive') }}</span>
              </label>
            </div>

            <div class="flex gap-3 pt-2">
              <button
                class="flex-1 rounded-full bg-[var(--color-secondary,#f59e0b)] py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
                :disabled="saving"
                @click="save"
              >
                {{ saving ? '…' : (editing ? t('adminZones.saveBtn') : t('adminZones.createBtn')) }}
              </button>
              <button class="rounded-full border border-slate-600 px-4 py-2 text-sm text-slate-300 hover:border-slate-400" @click="closeForm">
                {{ t('adminZones.cancelBtn') }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

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
const zones = ref([]);
const showForm = ref(false);
const editing = ref(null); // zone being edited, or null for create
const saving = ref(false);
const confirmDeleteId = ref(null); // zone id awaiting delete confirmation
const deletingId = ref(null);
const polygonJson = ref('[]');
const polygonError = ref('');
const feeTiersJson = ref('[]');
const feeTiersError = ref('');

const defaultForm = () => ({
  name: '',
  city: '',
  center_lat: null,
  center_lng: null,
  approx_radius_km: 5,
  is_active: true,
});
const form = ref(defaultForm());


const fetchZones = async () => {
  loading.value = true;
  fetchError.value = false;
  try {
    const res = await api.get('/admin/delivery-zones/');
    zones.value = res.data;
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
  }
};

const openCreate = () => {
  editing.value = null;
  form.value = defaultForm();
  polygonJson.value = '[]';
  polygonError.value = '';
  feeTiersJson.value = '[]';
  feeTiersError.value = '';
  showForm.value = true;
};

const openEdit = (zone) => {
  editing.value = zone;
  form.value = {
    name: zone.name,
    city: zone.city,
    center_lat: zone.center_lat,
    center_lng: zone.center_lng,
    approx_radius_km: zone.approx_radius_km,
    is_active: zone.is_active,
  };
  polygonJson.value = JSON.stringify(zone.polygon, null, 2);
  polygonError.value = '';
  feeTiersJson.value = JSON.stringify(zone.fee_tiers || [], null, 2);
  feeTiersError.value = '';
  showForm.value = true;
};

const closeForm = () => {
  showForm.value = false;
};

const save = async () => {
  polygonError.value = '';
  feeTiersError.value = '';
  let polygon;
  try {
    polygon = JSON.parse(polygonJson.value);
    if (!Array.isArray(polygon) || polygon.length < 3) throw new Error();
  } catch {
    polygonError.value = t('adminZones.polygonError');
    return;
  }
  let feeTiers = [];
  const tiersRaw = feeTiersJson.value?.trim();
  if (tiersRaw && tiersRaw !== '[]') {
    try {
      feeTiers = JSON.parse(tiersRaw);
      if (!Array.isArray(feeTiers)) throw new Error();
    } catch {
      feeTiersError.value = t('adminZones.feeTiersError');
      return;
    }
  }

  saving.value = true;
  try {
    const payload = { ...form.value, polygon, fee_tiers: feeTiers };
    if (editing.value) {
      const res = await api.patch(`/admin/delivery-zones/${editing.value.id}/`, payload);
      const idx = zones.value.findIndex(z => z.id === editing.value.id);
      if (idx >= 0) zones.value[idx] = res.data;
      toast.show(t('adminZones.saved'));
    } else {
      const res = await api.post('/admin/delivery-zones/', payload);
      zones.value.unshift(res.data);
      toast.show(t('adminZones.created'));
    }
    closeForm();
  } catch {
    toast.show(t('adminZones.saveFailed'), 'error');
  } finally {
    saving.value = false;
  }
};

const deleteZone = async (zone) => {
  deletingId.value = zone.id;
  try {
    await api.delete(`/admin/delivery-zones/${zone.id}/`);
    zones.value = zones.value.filter(z => z.id !== zone.id);
    confirmDeleteId.value = null;
    toast.show(t('adminZones.deleted'));
  } catch {
    toast.show(t('adminZones.deleteFailed'), 'error');
  } finally {
    deletingId.value = null;
  }
};

onMounted(fetchZones);
</script>

<style scoped>
.admin-input {
  @apply w-full rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-slate-500 focus:outline-none;
}
</style>
