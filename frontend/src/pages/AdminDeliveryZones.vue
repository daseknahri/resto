<template>
  <div class="ui-page-shell space-y-5">
    <!-- Page header -->
    <header class="ui-hero-ribbon ui-reveal px-4 py-3.5 md:px-5 md:py-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="ui-kicker">{{ t('adminZones.kicker') }}</p>
          <h1 class="text-xl font-semibold tracking-tight text-white md:text-2xl">
            {{ t('adminZones.title') }}
          </h1>
          <p class="ui-subtle mt-0.5 text-xs">{{ t('adminZones.subtitle') }}</p>
        </div>
        <button
          class="ui-btn-primary ui-press shrink-0 gap-1.5 px-4 py-2 text-xs"
          @click="openCreate"
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" class="h-3.5 w-3.5" fill="currentColor">
            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
          </svg>
          {{ t('adminZones.newZone') }}
        </button>
      </div>
    </header>

    <!-- Loading: skeleton table -->
    <div v-if="loading" class="ui-table-wrap">
      <table class="w-full min-w-[640px] text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-start">#</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t('adminZones.colName') }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t('adminZones.colCity') }}</th>
            <th scope="col" class="px-4 py-3 text-end">{{ t('adminZones.colRadius') }}</th>
            <th scope="col" class="px-4 py-3 text-center">{{ t('adminZones.colPolygon') }}</th>
            <th scope="col" class="px-4 py-3 text-center">{{ t('adminZones.colStatus') }}</th>
            <th scope="col" class="px-4 py-3 text-end">{{ t('adminZones.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr v-for="i in 4" :key="i" class="animate-pulse">
            <td class="px-4 py-3"><div class="h-3 w-4 rounded bg-slate-700/60" /></td>
            <td class="px-4 py-3"><div class="h-3 w-28 rounded bg-slate-700/60" /></td>
            <td class="px-4 py-3"><div class="h-3 w-20 rounded bg-slate-800/60" /></td>
            <td class="px-4 py-3"><div class="ms-auto h-3 w-10 rounded bg-slate-800/50" /></td>
            <td class="px-4 py-3"><div class="mx-auto h-3 w-10 rounded bg-slate-800/50" /></td>
            <td class="px-4 py-3"><div class="mx-auto h-4 w-14 rounded-full bg-slate-800/50" /></td>
            <td class="px-4 py-3"><div class="ms-auto h-3 w-16 rounded bg-slate-800/40" /></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Error -->
    <div
      v-else-if="fetchError"
      class="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/8 px-4 py-3"
      role="alert"
    >
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
      </svg>
      <p class="flex-1 text-sm text-red-300">{{ t('adminZones.fetchError') }}</p>
      <button
        class="shrink-0 rounded-lg border border-red-500/40 px-3 py-1 text-xs font-semibold text-red-300 transition hover:bg-red-500/10"
        @click="fetchZones"
      >{{ t('common.retry') }}</button>
    </div>

    <!-- Empty state -->
    <div v-else-if="!zones.length" class="ui-empty-state text-center p-6 space-y-1.5">
      <svg aria-hidden="true" viewBox="0 0 24 24" class="mx-auto mb-2 h-8 w-8 text-slate-500" fill="none" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
      </svg>
      <p class="text-sm font-semibold text-slate-100">{{ t('adminZones.emptyTitle') }}</p>
      <p class="text-xs text-slate-400">{{ t('adminZones.emptyBody') }}</p>
      <button
        class="ui-btn-primary mt-3 inline-flex gap-1.5 px-5 py-2 text-sm"
        @click="openCreate"
      >{{ t('adminZones.newZone') }}</button>
    </div>

    <!-- Zones table -->
    <div v-else class="ui-table-wrap">
      <table class="w-full min-w-[640px] text-sm">
        <thead class="bg-slate-800/60 text-xs text-slate-400">
          <tr>
            <th scope="col" class="px-4 py-3 text-start">#</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t('adminZones.colName') }}</th>
            <th scope="col" class="px-4 py-3 text-start">{{ t('adminZones.colCity') }}</th>
            <th scope="col" class="px-4 py-3 text-end">{{ t('adminZones.colRadius') }}</th>
            <th scope="col" class="px-4 py-3 text-center">{{ t('adminZones.colPolygon') }}</th>
            <th scope="col" class="px-4 py-3 text-center">{{ t('adminZones.colStatus') }}</th>
            <th scope="col" class="px-4 py-3 text-end">{{ t('adminZones.colActions') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-700/40">
          <tr
            v-for="(zone, index) in zones"
            :key="zone.id"
            class="ui-reveal transition-colors hover:bg-slate-800/30"
            :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
          >
            <td class="px-4 py-3 text-xs text-slate-500 tabular-nums">{{ zone.id }}</td>
            <td class="max-w-[180px] px-4 py-3 font-medium text-slate-200">
              <span class="block truncate">{{ zone.name }}</span>
            </td>
            <td class="px-4 py-3 text-slate-400">{{ zone.city }}</td>
            <td class="px-4 py-3 text-end text-slate-400 tabular-nums">{{ zone.approx_radius_km }} km</td>
            <td class="px-4 py-3 text-center text-xs text-slate-400 tabular-nums">
              {{ t('adminZones.polygonPts', { count: zone.polygon.length }) }}
            </td>
            <td class="px-4 py-3 text-center">
              <span
                class="rounded-full border px-2 py-0.5 text-[10px] font-semibold"
                :class="zone.is_active
                  ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
                  : 'border-slate-600 bg-slate-700/50 text-slate-400'"
              >
                {{ zone.is_active ? t('adminZones.active') : t('adminZones.inactive') }}
              </span>
            </td>
            <td class="px-4 py-3 text-end">
              <div class="flex items-center justify-end gap-1">
                <button
                  class="ui-press ui-touch-target inline-flex items-center rounded-lg px-2.5 text-xs font-medium text-sky-400 transition hover:bg-sky-400/10 hover:text-sky-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sky-400/60"
                  :aria-label="`${t('adminZones.edit')} ${zone.name}`"
                  @click="openEdit(zone)"
                >{{ t('adminZones.edit') }}</button>
                <button
                  class="ui-press ui-touch-target inline-flex items-center rounded-lg px-2.5 text-xs font-medium text-red-400 transition hover:bg-red-400/10 hover:text-red-300 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-400/60 disabled:opacity-50"
                  :disabled="deletingId === zone.id"
                  :aria-label="`${t('adminZones.delete')} ${zone.name}`"
                  @click="deleteZone(zone)"
                >{{ deletingId === zone.id ? '…' : t('adminZones.delete') }}</button>
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
          class="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-4 sm:items-center"
          @click.self="closeForm"
          @keydown.esc="closeForm"
        >
          <div
            ref="formDialogRef"
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-delivery-zones-form-dialog-title"
            class="w-full max-w-lg overflow-y-auto rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl shadow-black/50"
            style="max-height: 90dvh"
          >
            <h2
              id="admin-delivery-zones-form-dialog-title"
              class="text-base font-semibold text-white"
            >
              {{ editing ? t('adminZones.editTitle') : t('adminZones.createTitle') }}
            </h2>

            <div class="mt-4 space-y-3">
              <!-- Name -->
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1" for="az-name">
                  {{ t('adminZones.fieldName') }}
                </label>
                <input
                  id="az-name"
                  v-model="form.name"
                  type="text"
                  class="ui-input"
                  :placeholder="t('adminZones.namePlaceholder')"
                />
              </div>
              <!-- City -->
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1" for="az-city">
                  {{ t('adminZones.fieldCity') }}
                </label>
                <input
                  id="az-city"
                  v-model="form.city"
                  type="text"
                  class="ui-input"
                  :placeholder="t('adminZones.cityPlaceholder')"
                />
              </div>
              <!-- Centre coordinates -->
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs font-medium text-slate-400 mb-1" for="az-lat">
                    {{ t('adminZones.fieldCenterLat') }}
                  </label>
                  <input
                    id="az-lat"
                    v-model.number="form.center_lat"
                    type="number"
                    step="0.0001"
                    class="ui-input"
                    placeholder="48.8566"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-slate-400 mb-1" for="az-lng">
                    {{ t('adminZones.fieldCenterLng') }}
                  </label>
                  <input
                    id="az-lng"
                    v-model.number="form.center_lng"
                    type="number"
                    step="0.0001"
                    class="ui-input"
                    placeholder="2.3522"
                  />
                </div>
              </div>
              <!-- Approx radius -->
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1" for="az-radius">
                  {{ t('adminZones.fieldRadius') }}
                </label>
                <input
                  id="az-radius"
                  v-model.number="form.approx_radius_km"
                  type="number"
                  step="0.5"
                  min="0.5"
                  class="ui-input"
                  placeholder="5"
                />
              </div>
              <!-- Polygon JSON -->
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1" for="az-polygon">
                  {{ t('adminZones.fieldPolygon') }}
                  <span class="ms-1 text-slate-600">— JSON array of {lat, lng}</span>
                </label>
                <textarea
                  id="az-polygon"
                  v-model="polygonJson"
                  rows="5"
                  class="ui-textarea font-mono text-[11px] resize-y"
                  :placeholder='`[{"lat":48.86,"lng":2.34},{"lat":48.87,"lng":2.35},{"lat":48.85,"lng":2.36}]`'
                  :aria-invalid="polygonError ? 'true' : undefined"
                  aria-describedby="admin-zones-polygon-error"
                />
                <p
                  v-if="polygonError"
                  id="admin-zones-polygon-error"
                  class="mt-1 text-xs text-red-400"
                  role="alert"
                >{{ polygonError }}</p>
              </div>
              <!-- Fee tiers JSON -->
              <div>
                <label class="block text-xs font-medium text-slate-400 mb-1" for="az-fee-tiers">
                  {{ t('adminZones.fieldFeeTiers') }}
                  <span class="ms-1 text-slate-600">— JSON array of {km_up_to, fee}</span>
                </label>
                <textarea
                  id="az-fee-tiers"
                  v-model="feeTiersJson"
                  rows="3"
                  class="ui-textarea font-mono text-[11px] resize-y"
                  :placeholder='`[{"km_up_to":3,"fee":2.5},{"km_up_to":null,"fee":5.0}]`'
                  :aria-invalid="feeTiersError ? 'true' : undefined"
                  aria-describedby="admin-zones-fee-tiers-error"
                />
                <p
                  v-if="feeTiersError"
                  id="admin-zones-fee-tiers-error"
                  class="mt-1 text-xs text-red-400"
                  role="alert"
                >{{ feeTiersError }}</p>
                <p class="mt-0.5 text-[10px] text-slate-600">{{ t('adminZones.feeTiersHint') }}</p>
              </div>
              <!-- Active toggle -->
              <label class="flex cursor-pointer items-center gap-2.5 py-1">
                <input
                  v-model="form.is_active"
                  type="checkbox"
                  class="h-4 w-4 accent-[var(--color-secondary,#f59e0b)]"
                />
                <span class="text-sm text-slate-300">{{ t('adminZones.fieldActive') }}</span>
              </label>
            </div>

            <div class="mt-5 flex gap-3">
              <button
                class="ui-btn-primary flex-1 py-2 text-sm disabled:opacity-50"
                :disabled="saving"
                @click="save"
              >
                {{ saving ? '…' : (editing ? t('adminZones.saveBtn') : t('adminZones.createBtn')) }}
              </button>
              <button
                class="ui-btn-outline px-5 py-2 text-sm"
                @click="closeForm"
              >
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
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from '../composables/useI18n';
import { useConfirmModal } from '../composables/useConfirmModal';
import api from '../lib/api';
import { useToastStore } from '../stores/toast';

const { t } = useI18n();
const toast = useToastStore();

const loading = ref(true);
const fetchError = ref(false);
const zones = ref([]);
const showForm = ref(false);
const formDialogRef = ref(null);

const FOCUSABLE_DZ = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapFormFocus = (e) => {
  if (!formDialogRef.value || e.key !== 'Tab') return;
  const focusable = Array.from(formDialogRef.value.querySelectorAll(FOCUSABLE_DZ));
  if (!focusable.length) return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

watch(showForm, async (open) => {
  if (open) {
    await nextTick();
    formDialogRef.value?.querySelector(FOCUSABLE_DZ)?.focus();
    document.addEventListener('keydown', trapFormFocus);
  } else {
    document.removeEventListener('keydown', trapFormFocus);
  }
});
onBeforeUnmount(() => document.removeEventListener('keydown', trapFormFocus));
const editing = ref(null); // zone being edited, or null for create
const saving = ref(false);
const { confirm } = useConfirmModal();
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
  } catch (err) {
    toast.show(err?.response?.data?.detail || t('adminZones.saveFailed'), 'error');
  } finally {
    saving.value = false;
  }
};

const deleteZone = async (zone) => {
  const ok = await confirm({
    title: t('adminZones.deleteConfirm', { name: zone.name }),
    body: t('confirmModal.defaultBody'),
    confirmLabel: t('adminZones.delete'),
  });
  if (!ok) return;
  deletingId.value = zone.id;
  try {
    await api.delete(`/admin/delivery-zones/${zone.id}/`);
    zones.value = zones.value.filter(z => z.id !== zone.id);
    toast.show(t('adminZones.deleted'));
  } catch (err) {
    toast.show(err?.response?.data?.detail || t('adminZones.deleteFailed'), 'error');
  } finally {
    deletingId.value = null;
  }
};

onMounted(fetchZones);
</script>
