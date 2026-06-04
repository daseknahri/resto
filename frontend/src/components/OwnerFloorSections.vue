<template>
  <section class="ui-panel space-y-3 p-3 sm:p-4">
    <div class="flex items-center justify-between gap-2">
      <div class="min-w-0">
        <p class="text-sm font-semibold text-slate-200">{{ t('ownerSections.title') }}</p>
        <p class="text-xs text-slate-500">{{ t('ownerSections.subtitle') }}</p>
      </div>
      <button class="ui-btn-outline shrink-0 px-3 py-1.5 text-xs" @click="startCreate">
        + {{ t('ownerSections.add') }}
      </button>
    </div>

    <!-- Inline create -->
    <div v-if="creating" class="flex flex-wrap items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/50 p-2">
      <input
        v-model="newName"
        class="ui-input min-w-0 flex-1 text-sm"
        :placeholder="t('ownerSections.namePlaceholder')"
        :aria-label="t('ownerSections.namePlaceholder')"
        @keyup.enter="createSection"
      />
      <input v-model="newColor" type="color" class="h-8 w-10 shrink-0 rounded border border-slate-700 bg-transparent" :aria-label="t('ownerSections.color')" />
      <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="!newName.trim() || busy" @click="createSection">{{ t('common.save') }}</button>
      <button class="px-2 py-1.5 text-xs text-slate-400 hover:text-slate-200" @click="creating = false">{{ t('common.cancel') }}</button>
    </div>

    <p v-if="!sections.length && !creating" class="py-3 text-center text-xs text-slate-500">{{ t('ownerSections.empty') }}</p>

    <!-- Section list -->
    <div v-for="s in sections" :key="s.id" class="overflow-hidden rounded-xl border border-slate-800 bg-slate-950/50">
      <div class="flex items-center justify-between gap-2 p-3">
        <div class="flex min-w-0 items-center gap-2">
          <span class="h-3 w-3 shrink-0 rounded-full" :style="{ background: s.color || '#64748b' }" />
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-slate-100">{{ s.name }}</p>
            <p class="truncate text-xs text-slate-500">
              {{ t('ownerSections.tableCount', { n: s.tables.length }) }} ·
              <span v-if="s.servers.length" class="text-emerald-400/90">{{ s.servers.map((x) => x.name || x.email).join(', ') }}</span>
              <span v-else class="text-amber-400">{{ t('ownerSections.noWaiter') }}</span>
            </p>
          </div>
        </div>
        <div class="flex shrink-0 items-center gap-1.5">
          <button class="rounded-lg border border-slate-700 px-2.5 py-1 text-xs text-slate-300 hover:border-slate-500" @click="toggleEdit(s)">{{ t('common.edit') }}</button>
          <button class="rounded-lg border border-red-400/25 px-2.5 py-1 text-xs text-red-300 hover:border-red-400/50" @click="removeSection(s)">{{ t('common.delete') }}</button>
        </div>
      </div>

      <!-- Edit panel -->
      <div v-if="editId === s.id" class="space-y-3 border-t border-slate-800 p-3">
        <div class="flex items-center gap-2">
          <input v-model="editName" class="ui-input min-w-0 flex-1 text-sm" :aria-label="t('ownerSections.namePlaceholder')" />
          <input v-model="editColor" type="color" class="h-8 w-10 shrink-0 rounded border border-slate-700 bg-transparent" :aria-label="t('ownerSections.color')" />
        </div>

        <div>
          <p class="mb-1.5 text-xs font-semibold text-slate-400">{{ t('ownerSections.waiters') }}</p>
          <div class="flex flex-wrap gap-1.5">
            <label
              v-for="w in staff"
              :key="w.id"
              class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors"
              :class="editServers.includes(w.id) ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 text-slate-300 hover:border-slate-500'"
            >
              <input v-model="editServers" type="checkbox" :value="w.id" class="sr-only" />
              {{ w.name || w.email }}
            </label>
            <span v-if="!staff.length" class="text-xs text-slate-500">{{ t('ownerSections.noStaff') }}</span>
          </div>
        </div>

        <div>
          <p class="mb-1.5 text-xs font-semibold text-slate-400">{{ t('ownerSections.tables') }}</p>
          <div class="flex max-h-44 flex-wrap gap-1.5 overflow-y-auto">
            <label
              v-for="tb in tables"
              :key="tb.id"
              class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors"
              :class="editTables.includes(tb.id) ? 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : 'border-slate-700 text-slate-300 hover:border-slate-500'"
            >
              <input v-model="editTables" type="checkbox" :value="tb.id" class="sr-only" />
              {{ tb.label }}
            </label>
            <span v-if="!tables.length" class="text-xs text-slate-500">{{ t('ownerSections.noTables') }}</span>
          </div>
        </div>

        <div class="flex gap-2">
          <button class="ui-btn-primary px-3 py-1.5 text-xs" :disabled="busy || !editName.trim()" @click="saveSection(s)">{{ t('common.save') }}</button>
          <button class="px-2 py-1.5 text-xs text-slate-400 hover:text-slate-200" @click="editId = null">{{ t('common.cancel') }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import { useToastStore } from '../stores/toast';

defineProps({ tables: { type: Array, default: () => [] } });

const { t } = useI18n();
const toast = useToastStore();

const sections = ref([]);
const staff = ref([]);
const busy = ref(false);

const creating = ref(false);
const newName = ref('');
const newColor = ref('#f59e0b');

const editId = ref(null);
const editName = ref('');
const editColor = ref('#64748b');
const editServers = ref([]);
const editTables = ref([]);

const fetchSections = async () => {
  try {
    const { data } = await api.get('/owner/sections/');
    sections.value = data.sections || [];
  } catch { /* non-fatal */ }
};

const fetchStaff = async () => {
  try {
    const { data } = await api.get('/owner/staff/');
    staff.value = data.staff || data.results || (Array.isArray(data) ? data : []);
  } catch { /* non-fatal */ }
};

const startCreate = () => {
  creating.value = true;
  newName.value = '';
  newColor.value = '#f59e0b';
};

const createSection = async () => {
  if (!newName.value.trim() || busy.value) return;
  busy.value = true;
  try {
    await api.post('/owner/sections/', { name: newName.value.trim(), color: newColor.value });
    creating.value = false;
    await fetchSections();
  } catch {
    toast.show(t('ownerSections.saveError'), 'error');
  } finally {
    busy.value = false;
  }
};

const toggleEdit = (s) => {
  if (editId.value === s.id) { editId.value = null; return; }
  editId.value = s.id;
  editName.value = s.name;
  editColor.value = s.color || '#64748b';
  editServers.value = s.servers.map((x) => x.id);
  editTables.value = s.tables.map((x) => x.id);
};

const saveSection = async (s) => {
  if (busy.value || !editName.value.trim()) return;
  busy.value = true;
  try {
    await api.patch(`/owner/sections/${s.id}/`, {
      name: editName.value.trim(),
      color: editColor.value,
      table_ids: editTables.value,
      server_user_ids: editServers.value,
    });
    editId.value = null;
    await fetchSections();
  } catch {
    toast.show(t('ownerSections.saveError'), 'error');
  } finally {
    busy.value = false;
  }
};

const removeSection = async (s) => {
  if (!window.confirm(t('ownerSections.deleteConfirm', { name: s.name }))) return;
  busy.value = true;
  try {
    await api.delete(`/owner/sections/${s.id}/`);
    await fetchSections();
  } catch {
    toast.show(t('ownerSections.deleteError'), 'error');
  } finally {
    busy.value = false;
  }
};

onMounted(() => { fetchSections(); fetchStaff(); });
defineExpose({ fetchSections });
</script>
