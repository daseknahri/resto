<template>
  <section class="ui-panel space-y-3 p-3 sm:p-4" aria-labelledby="owner-sections-title">
    <!-- Header -->
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <p class="ui-kicker">{{ t('ownerSections.kicker') }}</p>
        <h2 id="owner-sections-title" class="text-base font-semibold text-white leading-tight">{{ t('ownerSections.title') }}</h2>
        <p class="mt-0.5 text-xs text-slate-400">{{ t('ownerSections.subtitle') }}</p>
      </div>
      <button
        class="ui-btn-outline ui-press ui-touch-target shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs"
        :aria-label="t('ownerSections.add')"
        @click="startCreate"
      >
        <AppIcon name="plus" class="h-3.5 w-3.5" aria-hidden="true" />
        {{ t('ownerSections.add') }}
      </button>
    </div>

    <!-- Inline create -->
    <Transition name="ui-fade">
      <div
        v-if="creating"
        class="space-y-2 rounded-2xl border border-slate-700/70 bg-slate-950/60 p-3"
        role="group"
        :aria-label="t('ownerSections.add')"
      >
        <div class="flex flex-wrap items-center gap-2">
          <input
            ref="newNameInputRef"
            v-model="newName"
            class="ui-input min-w-0 flex-1 text-sm"
            :placeholder="t('ownerSections.namePlaceholder')"
            :aria-label="t('ownerSections.namePlaceholder')"
            @keyup.enter="createSection"
          />
          <input
            v-model="newColor"
            type="color"
            class="h-9 w-10 shrink-0 cursor-pointer rounded-xl border border-slate-700 bg-transparent"
            :aria-label="t('ownerSections.color')"
          />
        </div>
        <div class="flex items-center gap-2">
          <button
            class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-xs"
            :disabled="!newName.trim() || busy"
            @click="createSection"
          >
            <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t('common.save') }}
          </button>
          <button
            class="ui-btn-outline ui-press inline-flex items-center gap-1 px-3 py-1.5 text-xs"
            @click="creating = false"
          >
            {{ t('common.cancel') }}
          </button>
        </div>
      </div>
    </Transition>

    <!-- Empty state -->
    <div
      v-if="!loading && !sections.length && !creating"
      class="ui-empty-state text-center"
    >
      <AppIcon name="table" class="mx-auto mb-2 h-8 w-8 text-slate-500" aria-hidden="true" />
      <p class="text-sm font-semibold text-slate-100">{{ t('ownerSections.emptyTitle') }}</p>
      <p class="mt-0.5 text-xs text-slate-400">{{ t('ownerSections.empty') }}</p>
      <button
        class="ui-btn-outline ui-press mt-3 inline-flex items-center gap-1.5 px-4 py-2 text-xs"
        @click="startCreate"
      >
        <AppIcon name="plus" class="h-3.5 w-3.5" aria-hidden="true" />
        {{ t('ownerSections.add') }}
      </button>
    </div>

    <!-- Loading skeletons -->
    <template v-if="loading">
      <div v-for="i in 2" :key="i" class="ui-skeleton h-14 rounded-xl" />
    </template>
    <!-- Section list -->
    <ul v-if="!loading" class="space-y-2">
    <li
      v-for="(s, index) in sections"
      :key="s.id"
      class="ui-surface-lift ui-reveal overflow-hidden rounded-xl border border-slate-800 bg-slate-950/50"
      :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
    >
      <div class="flex items-center justify-between gap-2 p-3">
        <div class="flex min-w-0 items-center gap-2.5">
          <span
            class="h-3.5 w-3.5 shrink-0 rounded-full shadow-sm"
            :style="{ background: s.color || '#64748b' }"
            aria-hidden="true"
          />
          <div class="min-w-0">
            <p class="truncate text-sm font-semibold text-slate-100">{{ s.name }}</p>
            <p class="truncate text-xs text-slate-500">
              <span class="tabular-nums">{{ t('ownerSections.tableCount', { n: s.tables.length }) }}</span>
              <span class="mx-1 text-slate-700" aria-hidden="true">·</span>
              <span v-if="s.servers.length" class="text-emerald-400/90">{{ s.servers.map((x) => x.name || x.email).join(', ') }}</span>
              <span v-else class="text-amber-400">{{ t('ownerSections.noWaiter') }}</span>
            </p>
          </div>
        </div>
        <div class="flex shrink-0 items-center gap-1">
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1 px-2.5 py-1 text-xs"
            :aria-label="editId === s.id ? `${t('common.close')} ${s.name}` : `${t('common.edit')} ${s.name}`"
            :aria-expanded="editId === s.id"
            :aria-controls="`section-edit-${s.id}`"
            @click="toggleEdit(s, $event.currentTarget)"
          >
            <AppIcon name="pencil" class="h-3.5 w-3.5" aria-hidden="true" />
            <span class="hidden sm:inline">{{ t('common.edit') }}</span>
          </button>
          <button
            class="ui-btn-outline ui-press ui-touch-target inline-flex items-center gap-1 px-2.5 py-1 text-xs text-red-300 border-[var(--color-danger)]/25 hover:border-[var(--color-danger)]/50"
            :aria-label="`${t('common.delete')} ${s.name}`"
            @click="deletingId = s.id"
          >
            <AppIcon name="trash" class="h-3.5 w-3.5" aria-hidden="true" />
            <span class="hidden sm:inline">{{ t('common.delete') }}</span>
          </button>
        </div>
      </div>

      <!-- Delete confirm panel -->
      <Transition name="ui-fade">
        <div
          v-if="deletingId === s.id"
          class="flex items-center justify-between gap-3 border-t border-rose-500/20 bg-rose-500/8 px-4 py-3"
          role="alert"
        >
          <p class="text-xs text-rose-200">{{ t('ownerSections.deleteConfirm', { name: s.name }) }}</p>
          <div class="flex shrink-0 gap-2">
            <button
              class="rounded-full border border-rose-500/40 bg-rose-500/20 px-3 py-1 text-[11px] font-semibold text-rose-200 hover:bg-rose-500/30 disabled:opacity-50"
              :disabled="busy"
              @click="removeSection(s)"
            >{{ t('ownerSections.deleteYes') }}</button>
            <button
              class="rounded-full border border-slate-600/60 px-3 py-1 text-[11px] font-semibold text-slate-400 hover:border-slate-500/60 hover:text-slate-300"
              :disabled="busy"
              @click="deletingId = null"
            >{{ t('common.back') }}</button>
          </div>
        </div>
      </Transition>

      <!-- Edit panel -->
      <Transition name="ui-fade">
        <div v-if="editId === s.id" :id="`section-edit-${s.id}`" class="space-y-3 border-t border-slate-800/80 bg-slate-950/30 p-3">
          <div class="flex items-center gap-2">
            <input
              v-model="editName"
              class="ui-input min-w-0 flex-1 text-sm"
              :aria-label="t('ownerSections.namePlaceholder')"
            />
            <input
              v-model="editColor"
              type="color"
              class="h-9 w-10 shrink-0 cursor-pointer rounded-xl border border-slate-700 bg-transparent"
              :aria-label="t('ownerSections.color')"
            />
          </div>

          <fieldset>
            <legend class="mb-1.5 text-xs font-semibold text-slate-400">{{ t('ownerSections.waiters') }}</legend>
            <div class="flex flex-wrap gap-1.5">
              <label
                v-for="w in staff"
                :key="w.id"
                class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors focus-within:ring-1 focus-within:ring-emerald-500/60"
                :class="editServers.includes(w.id) ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 text-slate-300 hover:border-slate-500'"
              >
                <input v-model="editServers" type="checkbox" :value="w.id" class="sr-only" />
                <AppIcon
                  v-if="editServers.includes(w.id)"
                  name="check"
                  class="h-3 w-3 shrink-0"
                  aria-hidden="true"
                />
                {{ w.name || w.email }}
              </label>
              <span v-if="!staff.length" class="text-xs text-slate-500">{{ t('ownerSections.noStaff') }}</span>
            </div>
          </fieldset>

          <fieldset>
            <legend class="mb-1.5 text-xs font-semibold text-slate-400">{{ t('ownerSections.tables') }}</legend>
            <div class="flex max-h-44 flex-wrap gap-1.5 overflow-y-auto" tabindex="0" :aria-label="t('ownerSections.tables')" role="group">
              <label
                v-for="tb in tables"
                :key="tb.id"
                class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors focus-within:ring-1 focus-within:ring-[var(--color-secondary)]/60"
                :class="editTables.includes(tb.id) ? 'border-[var(--color-secondary)]/50 bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : 'border-slate-700 text-slate-300 hover:border-slate-500'"
              >
                <input v-model="editTables" type="checkbox" :value="tb.id" class="sr-only" />
                <AppIcon
                  v-if="editTables.includes(tb.id)"
                  name="check"
                  class="h-3 w-3 shrink-0"
                  aria-hidden="true"
                />
                {{ tb.label }}
              </label>
              <span v-if="!tables.length" class="text-xs text-slate-500">{{ t('ownerSections.noTables') }}</span>
            </div>
          </fieldset>

          <div class="flex items-center gap-2 pt-0.5">
            <button
              class="ui-btn-primary ui-press inline-flex items-center gap-1.5 px-4 py-1.5 text-xs"
              :disabled="busy || !editName.trim()"
              @click="saveSection(s)"
            >
              <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
              {{ t('common.save') }}
            </button>
            <button
              class="ui-btn-outline ui-press inline-flex items-center gap-1 px-3 py-1.5 text-xs"
              @click="cancelEdit"
            >
              {{ t('common.cancel') }}
            </button>
          </div>
        </div>
      </Transition>
    </li>
    </ul>
  </section>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue';
import { useI18n } from '../composables/useI18n';
import api from '../lib/api';
import { useToastStore } from '../stores/toast';
import AppIcon from './AppIcon.vue';

defineProps({ tables: { type: Array, default: () => [] } });

const { t } = useI18n();
const toast = useToastStore();

const sections = ref([]);
const staff = ref([]);
const busy = ref(false);
const loading = ref(false);

const creating = ref(false);
const newName = ref('');
const newColor = ref('#f59e0b');
const newNameInputRef = ref(null);

const editId = ref(null);
const editName = ref('');
const editColor = ref('#64748b');
const editServers = ref([]);
const editTables = ref([]);
let _editTriggerEl = null;

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
  nextTick(() => newNameInputRef.value?.focus());
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

const toggleEdit = (s, triggerEl) => {
  if (editId.value === s.id) { editId.value = null; return; }
  _editTriggerEl = triggerEl || null;
  editId.value = s.id;
  editName.value = s.name;
  editColor.value = s.color || '#64748b';
  editServers.value = s.servers.map((x) => x.id);
  editTables.value = s.tables.map((x) => x.id);
};

const cancelEdit = () => {
  editId.value = null;
  nextTick(() => { _editTriggerEl?.focus(); _editTriggerEl = null; });
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
    nextTick(() => { _editTriggerEl?.focus(); _editTriggerEl = null; });
    await fetchSections();
  } catch {
    toast.show(t('ownerSections.saveError'), 'error');
  } finally {
    busy.value = false;
  }
};

const deletingId = ref(null);
const removeSection = async (s) => {
  busy.value = true;
  try {
    await api.delete(`/owner/sections/${s.id}/`);
    deletingId.value = null;
    await fetchSections();
  } catch {
    toast.show(t('ownerSections.deleteError'), 'error');
    deletingId.value = null;
  } finally {
    busy.value = false;
  }
};

onMounted(() => {
  loading.value = true;
  Promise.all([fetchSections(), fetchStaff()]).finally(() => {
    loading.value = false;
  });
});
defineExpose({ fetchSections });
</script>
