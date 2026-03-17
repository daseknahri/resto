<template>
  <div class="ui-panel space-y-5 p-5">
    <section class="ui-command-deck space-y-4 rounded-[26px] p-4 sm:p-5">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("stepSuperCategories.title") }}</p>
          <div class="space-y-2">
            <h2 class="text-xl font-semibold text-white sm:text-2xl">{{ t("stepSuperCategories.heading") }}</h2>
            <p class="max-w-2xl text-sm text-slate-300">{{ t("stepSuperCategories.description") }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <span class="ui-status-pill">
              <AppIcon name="filter" class="h-3.5 w-3.5" />
              {{ rows.length }} {{ t("stepSuperCategories.heading") }}
            </span>
            <span class="ui-status-pill">
              <AppIcon name="check" class="h-3.5 w-3.5" />
              {{ enabledCount }} {{ t("stepSuperCategories.enabledSummary") }}
            </span>
            <span class="ui-status-pill">
              <AppIcon name="close" class="h-3.5 w-3.5" />
              {{ disabledCount }} {{ t("stepSuperCategories.disabled") }}
            </span>
          </div>
        </div>

        <div class="flex flex-wrap gap-2 lg:justify-end">
          <button class="ui-btn-outline gap-2 px-4 py-2 text-sm" type="button" :disabled="saving" @click="saveAll">
            <AppIcon :name="saving ? 'refresh' : 'check'" class="h-4 w-4" />
            {{ saving ? t("common.saving") : t("common.save") }}
          </button>
          <button class="ui-btn-primary gap-2 px-4 py-2 text-sm" type="button" @click="openQuickModal">
            <AppIcon name="plus" class="h-4 w-4" />
            {{ t("stepSuperCategories.add") }}
          </button>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="ui-metric-card pl-5">
          <p class="ui-stat-label">{{ t("stepSuperCategories.title") }}</p>
          <p class="ui-stat-value text-2xl">{{ rows.length }}</p>
          <p class="ui-stat-note">{{ t("stepSuperCategories.heading") }}</p>
        </div>
        <div class="ui-metric-card pl-5">
          <p class="ui-stat-label">{{ t("stepSuperCategories.enabled") }}</p>
          <p class="ui-stat-value text-2xl">{{ enabledCount }}</p>
          <p class="ui-stat-note">{{ t("stepSuperCategories.enabledSummary") }}</p>
        </div>
        <div class="ui-metric-card pl-5">
          <p class="ui-stat-label">{{ t("stepSuperCategories.disabled") }}</p>
          <p class="ui-stat-value text-2xl">{{ disabledCount }}</p>
          <p class="ui-stat-note">{{ t("stepSuperCategories.disableToggle") }}</p>
        </div>
        <div class="ui-metric-card pl-5">
          <p class="ui-stat-label">{{ t("common.categories") }}</p>
          <p class="ui-stat-value text-2xl">{{ categoriesTotal }}</p>
          <p class="ui-stat-note">{{ t("common.categories") }} {{ t("common.available") }}</p>
        </div>
      </div>

      <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <label class="space-y-1 text-sm text-slate-300">
          <span class="sr-only">{{ t("common.search") }}</span>
          <div class="relative">
            <AppIcon name="search" class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input v-model.trim="search" class="ui-input pl-10" :placeholder="t('common.search')" />
          </div>
        </label>
        <div class="ui-scroll-row">
          <span class="ui-data-strip">{{ filteredRows.length }} / {{ rows.length }}</span>
          <span class="ui-data-strip">{{ enabledCount }} {{ t("stepSuperCategories.enabledSummary") }}</span>
          <span class="ui-data-strip">{{ categoriesTotal }} {{ t("common.categories") }}</span>
        </div>
      </div>
    </section>

    <div class="space-y-3">
      <div
        v-if="!filteredRows.length"
        class="ui-empty-state flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="relative z-10 flex items-start gap-3">
          <span class="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-700/70 bg-slate-900/75 text-brand-secondary shadow-lg shadow-black/25">
            <AppIcon :name="search ? 'search' : 'filter'" class="h-5 w-5" />
          </span>
          <div class="space-y-1">
            <p class="ui-kicker">{{ t("stepSuperCategories.title") }}</p>
            <h3 class="text-base font-semibold text-white">{{ search ? t("common.search") : t("stepSuperCategories.empty") }}</h3>
            <p class="max-w-xl text-sm text-slate-400">
              {{ search ? `${t("common.search")} - 0` : t("stepSuperCategories.description") }}
            </p>
          </div>
        </div>
        <button v-if="!search" class="ui-btn-primary relative z-10 gap-2 px-4 py-2 text-sm" type="button" @click="openQuickModal">
          <AppIcon name="plus" class="h-4 w-4" />
          {{ t("stepSuperCategories.add") }}
        </button>
      </div>

      <article
        v-for="(row, index) in filteredRows"
        :key="row.local_id"
        class="ui-selection-card p-4 sm:p-5"
        :data-warning="row.is_temporarily_disabled"
      >
        <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div class="min-w-0 flex-1 space-y-3">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="min-w-0 space-y-1">
                <p class="text-[11px] uppercase tracking-[0.2em] text-slate-500">{{ t("stepSuperCategories.cardLabel", { index: index + 1 }) }}</p>
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="truncate text-base font-semibold text-white sm:text-lg">{{ row.name || t("stepSuperCategories.namePlaceholder") }}</h3>
                  <span class="ui-route-badge">{{ row.slug || 'draft' }}</span>
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <span class="ui-state-chip" :data-active="row.is_published && !row.is_temporarily_disabled">
                  <AppIcon :name="row.is_published && !row.is_temporarily_disabled ? 'check' : 'close'" class="h-3.5 w-3.5" />
                  {{ row.is_temporarily_disabled ? t("stepSuperCategories.disabled") : (row.is_published ? t("stepSuperCategories.enabled") : t("common.soon")) }}
                </span>
              </div>
            </div>

            <p class="text-sm text-slate-300">
              {{ row.is_temporarily_disabled ? (row.disabled_note || t("stepSuperCategories.disabledNotePlaceholder")) : t("stepSuperCategories.description") }}
            </p>

            <div class="grid gap-2 sm:grid-cols-3">
              <div class="ui-admin-subcard">
                <p class="ui-stat-label">{{ t("stepSuperCategories.position") }}</p>
                <p class="mt-2 text-sm font-semibold text-white">{{ Number(row.position || 0) }}</p>
              </div>
              <div class="ui-admin-subcard">
                <p class="ui-stat-label">{{ t("common.categories") }}</p>
                <p class="mt-2 text-sm font-semibold text-white">{{ Number(row.category_count || 0) }}</p>
              </div>
              <div class="ui-admin-subcard">
                <p class="ui-stat-label">{{ t("stepSuperCategories.visibility") }}</p>
                <p class="mt-2 text-sm font-semibold text-white">{{ row.is_published ? t("common.available") : t("common.soon") }}</p>
              </div>
            </div>
          </div>

          <div class="flex flex-wrap gap-2 lg:w-auto lg:flex-col lg:items-stretch">
            <div class="flex flex-wrap gap-2 lg:grid lg:grid-cols-2">
              <button
                class="ui-btn-outline gap-2 px-3 py-2 text-xs sm:text-sm"
                type="button"
                :disabled="!canMoveUp(row.local_id)"
                @click="moveRow(row.local_id, -1)"
              >
                <AppIcon name="chevronUp" class="h-4 w-4" />
                {{ t("common.moveUp") }}
              </button>
              <button
                class="ui-btn-outline gap-2 px-3 py-2 text-xs sm:text-sm"
                type="button"
                :disabled="!canMoveDown(row.local_id)"
                @click="moveRow(row.local_id, 1)"
              >
                <AppIcon name="chevronDown" class="h-4 w-4" />
                {{ t("common.moveDown") }}
              </button>
            </div>
            <button class="ui-btn-outline gap-2 px-3 py-2 text-xs sm:text-sm" type="button" @click="openEditor(row.local_id)">
              <AppIcon name="settings" class="h-4 w-4" />
              {{ t("common.edit") }}
            </button>
            <button
              class="inline-flex items-center justify-center gap-2 rounded-full border border-red-400/25 px-3 py-2 text-xs text-red-200 transition hover:border-red-400/50 disabled:cursor-not-allowed disabled:opacity-50 sm:text-sm"
              type="button"
              :disabled="Number(row.category_count || 0) > 0"
              @click="removeByLocalId(row.local_id)"
            >
              <AppIcon name="close" class="h-4 w-4" />
              {{ t("common.remove") }}
            </button>
          </div>
        </div>
      </article>
    </div>

    <Teleport to="body">
      <div
        v-if="editorOpen && editingRow"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        @click.self="closeEditor"
      >
        <div class="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4 backdrop-blur sm:px-5">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("stepSuperCategories.title") }}</p>
              <h3 class="text-lg font-semibold text-white">{{ t("stepSuperCategories.edit") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline gap-2 px-3 py-1.5 text-xs" @click="closeEditor"><AppIcon name="close" class="h-3.5 w-3.5" />{{ t("common.close") }}</button>
          </div>

          <div class="space-y-4 p-4 sm:p-5">
            <div class="ui-scroll-row">
              <span class="ui-data-strip">{{ t("stepSuperCategories.position") }}: {{ Number(editingRow.position || 0) }}</span>
              <span class="ui-data-strip">{{ t("common.categories") }}: {{ Number(editingRow.category_count || 0) }}</span>
              <span class="ui-data-strip">{{ editingRow.slug || 'draft' }}</span>
            </div>

            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4 space-y-3">
              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepSuperCategories.namePlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`super-name-${locale.code}`"
                      type="button"
                      class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      :class="fieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                      @click="fieldLocales.name = locale.code"
                    >
                      {{ locale.nativeLabel }}
                    </button>
                  </div>
                </div>
                <input
                  :value="localizedFieldValue(editingRow, 'name', fieldLocales.name)"
                  class="ui-input"
                  :placeholder="t('stepSuperCategories.namePlaceholder')"
                  @input="setLocalizedFieldValue(editingRow, 'name', fieldLocales.name, $event.target.value)"
                />
                <p v-if="rowError(editingRow, 'name')" class="text-xs text-red-300">{{ rowError(editingRow, 'name') }}</p>
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <label class="space-y-1 text-sm text-slate-300">
                  <span class="text-xs text-slate-400">{{ t("stepSuperCategories.position") }}</span>
                  <input v-model.number="editingRow.position" type="number" min="0" class="ui-input" @input="clearRowError(editingRow.local_id, 'position')" />
                </label>
                <label class="space-y-1 text-sm text-slate-300">
                  <span class="text-xs text-slate-400">{{ t("stepSuperCategories.visibility") }}</span>
                  <select v-model="editingRow.is_published" class="ui-input">
                    <option :value="true">{{ t("common.available") }}</option>
                    <option :value="false">{{ t("common.soon") }}</option>
                  </select>
                </label>
              </div>

              <div class="rounded-2xl border border-slate-800 bg-slate-950/45 p-4 space-y-3">
                <label class="inline-flex items-center gap-2 text-sm text-slate-200">
                  <input v-model="editingRow.is_temporarily_disabled" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
                  {{ t("stepSuperCategories.disableToggle") }}
                </label>
                <label class="space-y-1 text-sm text-slate-300">
                  <span class="text-xs text-slate-400">{{ t("stepSuperCategories.disabledNote") }}</span>
                  <textarea
                    v-model.trim="editingRow.disabled_note"
                    rows="3"
                    class="ui-textarea"
                    :placeholder="t('stepSuperCategories.disabledNotePlaceholder')"
                  ></textarea>
                </label>
              </div>
            </div>
          </div>

          <div class="sticky bottom-0 z-10 flex justify-end border-t border-slate-800 bg-slate-950/95 px-4 py-4 backdrop-blur sm:px-5">
            <button type="button" class="ui-btn-primary gap-2 px-4 py-2 text-sm" @click="closeEditor"><AppIcon name="check" class="h-4 w-4" />{{ t("common.close") }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="quickModalOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
        @click.self="closeQuickModal"
      >
        <div class="w-full max-w-2xl rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4 backdrop-blur">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("stepSuperCategories.title") }}</p>
              <h3 class="text-lg font-semibold text-white">{{ t("stepSuperCategories.add") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline gap-2 px-3 py-1.5 text-xs" @click="closeQuickModal"><AppIcon name="close" class="h-3.5 w-3.5" />{{ t("common.close") }}</button>
          </div>
          <div class="space-y-4 p-4">
            <div class="ui-scroll-row">
              <span class="ui-data-strip"><AppIcon name="plus" class="h-3.5 w-3.5" />{{ t("stepSuperCategories.heading") }}</span>
              <span class="ui-data-strip">{{ t("stepSuperCategories.visibility") }}</span>
            </div>
            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4 space-y-3">
              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepSuperCategories.namePlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`quick-super-name-${locale.code}`"
                      type="button"
                      class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      :class="quickFieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                      @click="quickFieldLocales.name = locale.code"
                    >
                      {{ locale.nativeLabel }}
                    </button>
                  </div>
                </div>
                <input
                  :value="localizedQuickFieldValue('name', quickFieldLocales.name)"
                  class="ui-input"
                  :placeholder="t('stepSuperCategories.namePlaceholder')"
                  @input="setLocalizedQuickFieldValue('name', quickFieldLocales.name, $event.target.value)"
                />
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <input v-model.number="quickRow.position" type="number" min="0" class="ui-input" :placeholder="t('stepSuperCategories.position')" />
                <select v-model="quickRow.is_published" class="ui-input">
                  <option :value="true">{{ t("common.available") }}</option>
                  <option :value="false">{{ t("common.soon") }}</option>
                </select>
              </div>

              <label class="inline-flex items-center gap-2 text-sm text-slate-200">
                <input v-model="quickRow.is_temporarily_disabled" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
                {{ t("stepSuperCategories.disableToggle") }}
              </label>

              <textarea
                v-model.trim="quickRow.disabled_note"
                rows="3"
                class="ui-textarea"
                :placeholder="t('stepSuperCategories.disabledNotePlaceholder')"
              ></textarea>
            </div>
          </div>
          <div class="sticky bottom-0 z-10 flex justify-end gap-2 border-t border-slate-800 bg-slate-950/95 px-4 py-4 backdrop-blur">
            <button type="button" class="ui-btn-outline gap-2 px-4 py-2 text-sm" @click="closeQuickModal"><AppIcon name="close" class="h-4 w-4" />{{ t("common.close") }}</button>
            <button type="button" class="ui-btn-primary gap-2 px-4 py-2 text-sm" @click="quickAdd"><AppIcon name="plus" class="h-4 w-4" />{{ t("stepSuperCategories.add") }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <p v-if="globalError" class="text-sm text-red-300">{{ globalError }}</p>

    <div class="ui-toolbar-band flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 pt-3">
      <div class="flex flex-wrap gap-2 text-xs text-slate-400">
        <span class="ui-data-strip">{{ rows.length }} {{ t("stepSuperCategories.heading") }}</span>
        <span class="ui-data-strip">{{ enabledCount }} {{ t("stepSuperCategories.enabledSummary") }}</span>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <p class="text-sm text-slate-400">{{ status }}</p>
        <button class="ui-btn-primary gap-2 px-4 py-2" :disabled="saving" @click="saveAll">
          <AppIcon :name="saving ? 'refresh' : 'check'" class="h-4 w-4" />
          {{ saving ? t("common.saving") : t("common.save") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { superCategoryApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { LOCALE_OPTIONS, normalizeLocale } from "../i18n/config";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const rows = reactive([]);
const removedIds = ref([]);
const rowErrors = reactive({});
const globalError = ref("");
const saving = ref(false);
const status = ref("");
const search = ref("");
const quickModalOpen = ref(false);
const editorOpen = ref(false);
const editorLocalId = ref("");
const tenant = useTenantStore();
const toast = useToastStore();
const { t } = useI18n();

const fieldLocales = reactive({ name: "en" });
const quickFieldLocales = reactive({ name: "en" });
const quickRow = reactive({
  local_id: "quick-super-category",
  name: "",
  name_i18n: {},
  position: 0,
  is_published: true,
  is_temporarily_disabled: false,
  disabled_note: "",
  category_count: 0,
});

const maxTranslationLocales = computed(() => Math.max(0, Number(tenant.entitlements?.max_languages || 1) - 1));
const defaultLocale = computed(() => normalizeLocale(tenant.resolvedMeta?.profile?.language || "en"));
const availableContentLocales = computed(() => {
  const primary = LOCALE_OPTIONS.find((option) => option.code === defaultLocale.value) || LOCALE_OPTIONS[0];
  const secondary = LOCALE_OPTIONS.filter((option) => option.code !== primary.code).slice(0, maxTranslationLocales.value);
  return [primary, ...secondary];
});
const enabledCount = computed(() => rows.filter((row) => row.is_published && !row.is_temporarily_disabled).length);
const disabledCount = computed(() => rows.filter((row) => row.is_temporarily_disabled).length);
const categoriesTotal = computed(() => rows.reduce((sum, row) => sum + Number(row.category_count || 0), 0));
const editingRow = computed(() => rows.find((row) => String(row.local_id) === String(editorLocalId.value)) || null);
const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase();
  const source = [...rows].sort((a, b) => (Number(a.position || 0) - Number(b.position || 0)) || String(a.name || "").localeCompare(String(b.name || "")));
  if (!query) return source;
  return source.filter((row) => [row.name, row.slug, row.disabled_note].filter(Boolean).some((value) => String(value).toLowerCase().includes(query)));
});
const orderedRows = computed(() => [...rows].sort((a, b) => (Number(a.position || 0) - Number(b.position || 0)) || String(a.name || "").localeCompare(String(b.name || ""))));

const syncFieldLocales = () => {
  const allowed = new Set(availableContentLocales.value.map((locale) => locale.code));
  if (!allowed.has(fieldLocales.name)) fieldLocales.name = defaultLocale.value;
  if (!allowed.has(quickFieldLocales.name)) quickFieldLocales.name = defaultLocale.value;
};
watch([availableContentLocales, defaultLocale], syncFieldLocales, { immediate: true });

const normalizeRow = (row = {}) => ({
  id: row.id,
  local_id: row.id || crypto.randomUUID(),
  name: row.name || "",
  name_i18n: row.name_i18n && typeof row.name_i18n === "object" ? { ...row.name_i18n } : {},
  slug: row.slug || "",
  position: row.position ?? rows.length,
  is_published: row.is_published ?? true,
  is_temporarily_disabled: row.is_temporarily_disabled === true,
  disabled_note: row.disabled_note || "",
  category_count: Number(row.category_count || 0),
});

const pickI18nMap = (input, allowedLocales = null) => {
  const out = {};
  if (!input || typeof input !== "object") return out;
  const allowed = Array.isArray(allowedLocales) ? new Set(allowedLocales.map((locale) => String(locale || "").trim().toLowerCase())) : null;
  Object.entries(input).forEach(([rawLocale, rawValue]) => {
    const locale = String(rawLocale || "").trim().toLowerCase();
    const value = String(rawValue || "").trim();
    if (!locale || !value) return;
    if (allowed && !allowed.has(locale)) return;
    out[locale] = value;
  });
  return out;
};

const localizedFieldValue = (row, field, localeCode) => {
  if (!row) return "";
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(row[field] || "");
  const map = row[`${field}_i18n`];
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};
const setLocalizedFieldValue = (row, field, localeCode, value) => {
  if (!row) return;
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    row[field] = nextValue;
  } else {
    const mapField = `${field}_i18n`;
    if (!row[mapField] || typeof row[mapField] !== "object") row[mapField] = {};
    if (nextValue.trim()) row[mapField][locale] = nextValue;
    else delete row[mapField][locale];
  }
  clearRowError(row.local_id, field);
};

const localizedQuickFieldValue = (field, localeCode) => {
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(quickRow[field] || "");
  const map = quickRow[`${field}_i18n`];
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};
const setLocalizedQuickFieldValue = (field, localeCode, value) => {
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    quickRow[field] = nextValue;
  } else {
    const mapField = `${field}_i18n`;
    if (!quickRow[mapField] || typeof quickRow[mapField] !== "object") quickRow[mapField] = {};
    if (nextValue.trim()) quickRow[mapField][locale] = nextValue;
    else delete quickRow[mapField][locale];
  }
};

const rowError = (row, field) => rowErrors[row.local_id]?.[field] || "";
const setRowError = (localId, field, message) => {
  rowErrors[localId] = { ...(rowErrors[localId] || {}), [field]: message };
};
const clearRowError = (localId, field) => {
  if (!rowErrors[localId]?.[field]) return;
  const next = { ...rowErrors[localId] };
  delete next[field];
  if (Object.keys(next).length) rowErrors[localId] = next;
  else delete rowErrors[localId];
};
const clearAllErrors = () => {
  Object.keys(rowErrors).forEach((key) => delete rowErrors[key]);
  globalError.value = "";
};

const validateClient = () => {
  clearAllErrors();
  const filled = rows.filter((row) => row.name?.trim());
  if (!filled.length) {
    globalError.value = t("stepSuperCategories.empty");
    return false;
  }
  const names = new Map();
  let valid = true;
  for (const row of filled) {
    const name = String(row.name || "").trim();
    if (name.length < 2) {
      setRowError(row.local_id, "name", t("stepSuperCategories.nameMin"));
      valid = false;
    }
    const key = name.toLowerCase();
    if (names.has(key)) {
      setRowError(row.local_id, "name", t("stepSuperCategories.duplicateName"));
      setRowError(names.get(key), "name", t("stepSuperCategories.duplicateName"));
      valid = false;
    } else {
      names.set(key, row.local_id);
    }
    if (Number(row.position) < 0) {
      setRowError(row.local_id, "position", t("stepSuperCategories.positionMin"));
      valid = false;
    }
  }
  return valid;
};

const renumberRows = (collection) => {
  collection.forEach((row, index) => {
    row.position = index;
  });
};

const canMoveUp = (localId) => orderedRows.value.findIndex((row) => String(row.local_id) === String(localId)) > 0;
const canMoveDown = (localId) => {
  const index = orderedRows.value.findIndex((row) => String(row.local_id) === String(localId));
  return index > -1 && index < orderedRows.value.length - 1;
};

const moveRow = (localId, direction) => {
  const ordered = [...orderedRows.value];
  const index = ordered.findIndex((row) => String(row.local_id) === String(localId));
  const targetIndex = index + direction;
  if (index < 0 || targetIndex < 0 || targetIndex >= ordered.length) return;
  [ordered[index], ordered[targetIndex]] = [ordered[targetIndex], ordered[index]];
  renumberRows(ordered);
};

const load = async () => {
  try {
    const data = await superCategoryApi.list();
    const normalized = Array.isArray(data) ? data.map(normalizeRow) : [];
    rows.splice(0, rows.length, ...normalized);
  } catch {
    rows.splice(0, rows.length);
    status.value = t("common.loadFailed");
  }
};

const openEditor = (localId) => {
  editorLocalId.value = String(localId || "");
  editorOpen.value = true;
};
const closeEditor = () => {
  editorOpen.value = false;
  editorLocalId.value = "";
};
const openQuickModal = () => {
  quickRow.name = "";
  quickRow.name_i18n = {};
  quickRow.position = rows.length;
  quickRow.is_published = true;
  quickRow.is_temporarily_disabled = false;
  quickRow.disabled_note = "";
  quickFieldLocales.name = defaultLocale.value;
  quickModalOpen.value = true;
};
const closeQuickModal = () => {
  quickModalOpen.value = false;
};

const quickAdd = () => {
  const name = String(quickRow.name || "").trim();
  if (name.length < 2) {
    toast.show(t("stepSuperCategories.nameMin"), "error");
    return;
  }
  const allowedTranslationLocales = availableContentLocales.value.map((locale) => locale.code).filter((locale) => locale !== defaultLocale.value);
  rows.push(normalizeRow({
    name,
    name_i18n: pickI18nMap(quickRow.name_i18n, allowedTranslationLocales),
    position: orderedRows.value.length,
    is_published: quickRow.is_published,
    is_temporarily_disabled: quickRow.is_temporarily_disabled,
    disabled_note: String(quickRow.disabled_note || "").trim(),
  }));
  closeQuickModal();
};

const removeByLocalId = async (localId) => {
  const index = rows.findIndex((row) => row.local_id === localId);
  if (index < 0) return;
  const [row] = rows.splice(index, 1);
  if (row?.id) removedIds.value.push(row.id);
  if (String(editorLocalId.value) === String(localId)) closeEditor();
  delete rowErrors[localId];
  renumberRows(orderedRows.value);
};

const mapServerErrorsToRow = (localId, fieldErrors = {}) => {
  Object.entries(fieldErrors).forEach(([field, message]) => setRowError(localId, field, message));
};

const saveAll = async () => {
  saving.value = true;
  status.value = "";
  if (!validateClient()) {
    status.value = t("stepSuperCategories.fixValidation");
    saving.value = false;
    return;
  }
  try {
    const validRows = rows.filter((row) => row.name?.trim());
    const allowedTranslationLocales = availableContentLocales.value.map((locale) => locale.code).filter((locale) => locale !== defaultLocale.value);
    for (const row of validRows) {
      try {
        const saved = await superCategoryApi.upsert({
          ...row,
          position: Number(row.position) || 0,
          name_i18n: pickI18nMap(row.name_i18n, allowedTranslationLocales),
          disabled_note: String(row.disabled_note || "").trim(),
        });
        row.id = saved.id;
        row.slug = saved.slug;
        row.category_count = Number(saved.category_count || row.category_count || 0);
      } catch (error) {
        mapServerErrorsToRow(row.local_id, error?.fieldErrors || {});
        throw error;
      }
    }
    for (const id of removedIds.value) {
      await superCategoryApi.remove(id);
    }
    removedIds.value = [];
    status.value = t("common.saved");
    toast.show(t("stepSuperCategories.savedToast"), "success");
  } catch (error) {
    status.value = t("common.saveFailed");
    globalError.value = error?.message || t("stepSuperCategories.saveFailed");
    toast.show(globalError.value, "error");
  } finally {
    saving.value = false;
  }
};

onMounted(load);
</script>


