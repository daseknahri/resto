<template>
  <div class="ui-panel space-y-5 p-5">
    <section class="ui-section-band space-y-4 rounded-[26px] p-4 sm:p-5">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("stepCategories.title") }}</p>
          <h2 class="text-xl font-semibold text-white sm:text-2xl">{{ t("common.categories") }}</h2>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="ui-btn-outline px-4 py-2 text-sm" type="button" :disabled="saving || !superCategoryOptions.length" @click="saveAll">
            {{ saving ? t("common.saving") : t("common.save") }}
          </button>
          <button class="ui-btn-primary px-4 py-2 text-sm" type="button" :disabled="!superCategoryOptions.length" @click="openQuickModal">
            {{ t("stepCategories.addCategory") }}
          </button>
        </div>
      </div>

      <div v-if="!superCategoryOptions.length" class="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 text-sm text-amber-100">
        {{ t("stepCategories.addSuperCategoriesFirst") }}
      </div>

      <template v-else>
        <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
          <label class="space-y-1 text-sm text-slate-300">
            <span class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{{ t("stepCategories.selectSuperCategory") }}</span>
            <select v-model="activeSuperCategoryId" class="ui-input border-slate-700 bg-slate-950/70">
              <option v-for="group in sortedSuperCategoryOptions" :key="group.id" :value="String(group.id)">{{ superCategoryLabel(group) }}</option>
            </select>
          </label>
          <label class="text-sm text-slate-300">
            <span class="sr-only">{{ t("common.search") }}</span>
            <input v-model.trim="search" class="ui-input border-slate-700 bg-slate-950/70" :placeholder="t('common.search')" />
          </label>
          <div class="ui-scroll-row">
            <span class="ui-data-strip">{{ filteredCategories.length }} / {{ activeCategories.length }} {{ t("common.categories") }}</span>
            <span class="ui-data-strip">{{ activeSuperCategoryRecord?.name || '' }}</span>
          </div>
        </div>
      </template>
    </section>

    <div class="space-y-3">
      <div
        v-if="superCategoryOptions.length && !filteredCategories.length"
        class="rounded-2xl border border-dashed border-slate-700 bg-slate-950/55 p-5 text-sm text-slate-400"
      >
        {{ search ? `${t("common.search")} - 0` : t("stepCategories.addAtLeastOne") }}
      </div>

      <article
        v-for="(cat, index) in filteredCategories"
        :key="cat.local_id"
        class="rounded-2xl border border-slate-800 bg-slate-950/75 p-4 shadow-[0_12px_28px_rgba(2,8,23,0.18)]"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <p class="text-[11px] uppercase tracking-[0.2em] text-slate-500">{{ t("stepCategories.cardLabel", { index: index + 1 }) }}</p>
            <h3 class="mt-1 truncate text-base font-semibold text-white">{{ cat.name || t("stepCategories.categoryNamePlaceholder") }}</h3>
            <p class="mt-1 line-clamp-2 text-sm text-slate-400">{{ cat.description || t("stepCategories.categoryDescriptionPlaceholder") }}</p>
            <div class="mt-2 flex flex-wrap gap-2">
              <span class="ui-data-strip">Pos: {{ Number(cat.position || 0) }}</span>
              <span class="ui-data-strip">{{ t("stepCategories.translationsTitle") }}: {{ Object.keys(cat.name_i18n || {}).length }}</span>
            </div>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" type="button" @click="openEditor(cat.local_id)">
            {{ t("common.edit") }}
          </button>
          <button class="rounded-full border border-red-400/25 px-3 py-1.5 text-xs text-red-200 hover:border-red-400/50" type="button" @click="removeByLocalId(cat.local_id)">
            {{ t("common.remove") }}
          </button>
        </div>
      </article>
    </div>

    <Teleport to="body">
      <div
        v-if="editorOpen && editingCategory"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        @click.self="closeEditor"
      >
        <div class="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4 backdrop-blur sm:px-5">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("common.categories") }}</p>
              <h3 class="text-lg font-semibold text-white">{{ t("common.edit") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeEditor">{{ t("common.close") }}</button>
          </div>

          <div class="space-y-4 p-4 sm:p-5">
            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4 space-y-3">
              <label class="space-y-1 text-sm text-slate-300">
                <span class="text-xs text-slate-400">{{ t("stepCategories.selectSuperCategory") }}</span>
                <select v-model="editingCategory.super_category" class="ui-input">
                  <option v-for="group in sortedSuperCategoryOptions" :key="group.id" :value="Number(group.id)">{{ superCategoryLabel(group) }}</option>
                </select>
              </label>

              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepCategories.categoryNamePlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`cat-name-${locale.code}`"
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
                  :value="localizedFieldValue(editingCategory, 'name', fieldLocales.name)"
                  class="ui-input"
                  :placeholder="t('stepCategories.categoryNamePlaceholder')"
                  @input="setLocalizedFieldValue(editingCategory, 'name', fieldLocales.name, $event.target.value)"
                />
                <p v-if="rowError(editingCategory, 'name')" class="text-xs text-red-300">{{ rowError(editingCategory, 'name') }}</p>
              </div>

              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepCategories.categoryDescriptionPlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`cat-desc-${locale.code}`"
                      type="button"
                      class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      :class="fieldLocales.description === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                      @click="fieldLocales.description = locale.code"
                    >
                      {{ locale.nativeLabel }}
                    </button>
                  </div>
                </div>
                <textarea
                  :value="localizedFieldValue(editingCategory, 'description', fieldLocales.description)"
                  rows="3"
                  class="ui-textarea"
                  :placeholder="t('stepCategories.categoryDescriptionPlaceholder')"
                  @input="setLocalizedFieldValue(editingCategory, 'description', fieldLocales.description, $event.target.value)"
                ></textarea>
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <label class="space-y-1 text-sm text-slate-300">
                  <span class="text-xs text-slate-400">{{ t("stepCategories.positionMin") }}</span>
                  <input v-model.number="editingCategory.position" type="number" min="0" class="ui-input" @input="clearRowError(editingCategory.local_id, 'position')" />
                </label>
                <label class="space-y-1 text-sm text-slate-300">
                  <span class="text-xs text-slate-400">{{ t("stepCategories.visibility") }}</span>
                  <select v-model="editingCategory.is_published" class="ui-input">
                    <option :value="true">{{ t("common.available") }}</option>
                    <option :value="false">{{ t("common.soon") }}</option>
                  </select>
                </label>
              </div>
            </div>
          </div>

          <div class="sticky bottom-0 z-10 flex justify-end border-t border-slate-800 bg-slate-950/95 px-4 py-4 backdrop-blur sm:px-5">
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="closeEditor">{{ t("common.close") }}</button>
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
              <p class="ui-kicker">{{ t("common.categories") }}</p>
              <h3 class="text-lg font-semibold text-white">{{ t("stepCategories.addCategory") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeQuickModal">{{ t("common.close") }}</button>
          </div>
          <div class="space-y-4 p-4">
            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4 space-y-3">
              <label class="space-y-1 text-sm text-slate-300">
                <span class="text-xs text-slate-400">{{ t("stepCategories.selectSuperCategory") }}</span>
                <select v-model="quickCategory.super_category" class="ui-input">
                  <option v-for="group in sortedSuperCategoryOptions" :key="group.id" :value="Number(group.id)">{{ superCategoryLabel(group) }}</option>
                </select>
              </label>

              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepCategories.categoryNamePlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`quick-cat-name-${locale.code}`"
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
                  :placeholder="t('stepCategories.categoryNamePlaceholder')"
                  @input="setLocalizedQuickFieldValue('name', quickFieldLocales.name, $event.target.value)"
                />
              </div>

              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepCategories.categoryDescriptionPlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`quick-cat-desc-${locale.code}`"
                      type="button"
                      class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      :class="quickFieldLocales.description === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                      @click="quickFieldLocales.description = locale.code"
                    >
                      {{ locale.nativeLabel }}
                    </button>
                  </div>
                </div>
                <textarea
                  :value="localizedQuickFieldValue('description', quickFieldLocales.description)"
                  rows="3"
                  class="ui-textarea"
                  :placeholder="t('stepCategories.categoryDescriptionPlaceholder')"
                  @input="setLocalizedQuickFieldValue('description', quickFieldLocales.description, $event.target.value)"
                ></textarea>
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <input v-model.number="quickCategory.position" type="number" min="0" class="ui-input" :placeholder="t('stepCategories.positionMin')" />
                <select v-model="quickCategory.is_published" class="ui-input">
                  <option :value="true">{{ t("common.available") }}</option>
                  <option :value="false">{{ t("common.soon") }}</option>
                </select>
              </div>
            </div>
          </div>
          <div class="sticky bottom-0 z-10 flex justify-end gap-2 border-t border-slate-800 bg-slate-950/95 px-4 py-4 backdrop-blur">
            <button type="button" class="ui-btn-outline px-4 py-2 text-sm" @click="closeQuickModal">{{ t("common.close") }}</button>
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="quickAdd">{{ t("stepCategories.addCategory") }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <p v-if="globalError" class="text-sm text-red-300">{{ globalError }}</p>

    <div class="flex flex-wrap items-center gap-3 border-t border-slate-800/80 pt-3">
      <button class="ui-btn-primary px-4 py-2" :disabled="saving || !superCategoryOptions.length" @click="saveAll">
        {{ saving ? t("common.saving") : props.standalone ? t("common.save") : t("common.saveAndNext") }}
      </button>
      <button v-if="!props.standalone" class="ui-btn-outline px-4 py-2" @click="$emit('back')">{{ t("common.previous") }}</button>
      <p class="text-sm text-slate-400">{{ status }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { categoryApi, superCategoryApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { LOCALE_OPTIONS, normalizeLocale } from "../i18n/config";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const props = defineProps({ standalone: { type: Boolean, default: false } });
const emit = defineEmits(["next", "back"]);
const { t } = useI18n();
const tenant = useTenantStore();
const toast = useToastStore();

const categories = reactive([]);
const removedIds = ref([]);
const rowErrors = reactive({});
const globalError = ref("");
const saving = ref(false);
const status = ref("");
const search = ref("");
const superCategoryOptions = ref([]);
const activeSuperCategoryId = ref("");
const editorOpen = ref(false);
const editorLocalId = ref("");
const fieldLocales = reactive({ name: "en", description: "en" });
const quickFieldLocales = reactive({ name: "en", description: "en" });
const quickModalOpen = ref(false);
const quickCategory = reactive({
  local_id: "quick-category",
  super_category: "",
  name: "",
  name_i18n: {},
  description: "",
  description_i18n: {},
  position: 0,
  is_published: true,
});

const maxTranslationLocales = computed(() => Math.max(0, Number(tenant.entitlements?.max_languages || 1) - 1));
const defaultLocale = computed(() => normalizeLocale(tenant.resolvedMeta?.profile?.language || "en"));
const availableContentLocales = computed(() => {
  const primary = LOCALE_OPTIONS.find((option) => option.code === defaultLocale.value) || LOCALE_OPTIONS[0];
  const secondary = LOCALE_OPTIONS.filter((option) => option.code !== primary.code).slice(0, maxTranslationLocales.value);
  return [primary, ...secondary];
});
const sortedSuperCategoryOptions = computed(() => [...superCategoryOptions.value].sort((a, b) => (a.position || 0) - (b.position || 0) || String(a.name || "").localeCompare(String(b.name || ""))));
const activeSuperCategoryRecord = computed(() => sortedSuperCategoryOptions.value.find((group) => String(group.id) === String(activeSuperCategoryId.value)) || null);
const activeCategories = computed(() => categories.filter((cat) => String(cat.super_category) === String(activeSuperCategoryId.value)));
const filteredCategories = computed(() => {
  const query = search.value.trim().toLowerCase();
  if (!query) return activeCategories.value;
  return activeCategories.value.filter((cat) => [cat.name, cat.description, cat.slug].filter(Boolean).some((value) => String(value).toLowerCase().includes(query)));
});
const editingCategory = computed(() => categories.find((cat) => String(cat.local_id) === String(editorLocalId.value)) || null);

const syncFieldLocales = () => {
  const allowed = new Set(availableContentLocales.value.map((locale) => locale.code));
  if (!allowed.has(fieldLocales.name)) fieldLocales.name = defaultLocale.value;
  if (!allowed.has(fieldLocales.description)) fieldLocales.description = defaultLocale.value;
  if (!allowed.has(quickFieldLocales.name)) quickFieldLocales.name = defaultLocale.value;
  if (!allowed.has(quickFieldLocales.description)) quickFieldLocales.description = defaultLocale.value;
};
watch([availableContentLocales, defaultLocale], syncFieldLocales, { immediate: true });

const normalizeCategory = (cat = {}) => ({
  id: cat.id,
  local_id: cat.id || crypto.randomUUID(),
  super_category: cat.super_category ? String(cat.super_category) : "",
  super_category_slug: cat.super_category_slug || "",
  super_category_name: cat.super_category_name || "",
  name: cat.name || "",
  name_i18n: cat.name_i18n && typeof cat.name_i18n === "object" ? { ...cat.name_i18n } : {},
  slug: cat.slug || "",
  description: cat.description || "",
  description_i18n: cat.description_i18n && typeof cat.description_i18n === "object" ? { ...cat.description_i18n } : {},
  position: cat.position ?? categories.length,
  is_published: cat.is_published ?? true,
});

const superCategoryLabel = (group) => {
  if (!group) return "";
  const status = group.is_temporarily_disabled ? t("stepSuperCategories.disabled") : null;
  return status ? `${group.name} · ${status}` : String(group.name || "");
};

const syncActiveSuperCategory = () => {
  if (!sortedSuperCategoryOptions.value.length) {
    activeSuperCategoryId.value = "";
    return;
  }
  const exists = sortedSuperCategoryOptions.value.some((group) => String(group.id) === String(activeSuperCategoryId.value));
  if (!exists) {
    activeSuperCategoryId.value = String(sortedSuperCategoryOptions.value[0].id);
  }
};
watch(sortedSuperCategoryOptions, syncActiveSuperCategory, { immediate: true });

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

const localizedFieldValue = (cat, field, localeCode) => {
  if (!cat) return "";
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(cat[field] || "");
  const map = cat[`${field}_i18n`];
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};
const setLocalizedFieldValue = (cat, field, localeCode, value) => {
  if (!cat) return;
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    cat[field] = nextValue;
  } else {
    const mapField = `${field}_i18n`;
    if (!cat[mapField] || typeof cat[mapField] !== "object") cat[mapField] = {};
    if (nextValue.trim()) cat[mapField][locale] = nextValue;
    else delete cat[mapField][locale];
  }
  clearRowError(cat.local_id, field);
};
const localizedQuickFieldValue = (field, localeCode) => {
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(quickCategory[field] || "");
  const map = quickCategory[`${field}_i18n`];
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};
const setLocalizedQuickFieldValue = (field, localeCode, value) => {
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    quickCategory[field] = nextValue;
  } else {
    const mapField = `${field}_i18n`;
    if (!quickCategory[mapField] || typeof quickCategory[mapField] !== "object") quickCategory[mapField] = {};
    if (nextValue.trim()) quickCategory[mapField][locale] = nextValue;
    else delete quickCategory[mapField][locale];
  }
};

const rowError = (cat, field) => rowErrors[cat.local_id]?.[field] || "";
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
  const filled = categories.filter((cat) => cat.name?.trim());
  if (!filled.length) {
    globalError.value = t("stepCategories.addAtLeastOne");
    return false;
  }
  const namesByGroup = new Map();
  let valid = true;
  for (const cat of filled) {
    const name = String(cat.name || "").trim();
    if (name.length < 2) {
      setRowError(cat.local_id, "name", t("stepCategories.nameMin"));
      valid = false;
    }
    if (!cat.super_category) {
      setRowError(cat.local_id, "super_category", t("stepCategories.superCategoryRequired"));
      valid = false;
    }
    const nameKey = `${cat.super_category}::${name.toLowerCase()}`;
    if (namesByGroup.has(nameKey)) {
      setRowError(cat.local_id, "name", t("stepCategories.duplicateName"));
      setRowError(namesByGroup.get(nameKey), "name", t("stepCategories.duplicateName"));
      valid = false;
    } else {
      namesByGroup.set(nameKey, cat.local_id);
    }
    if (Number(cat.position) < 0) {
      setRowError(cat.local_id, "position", t("stepCategories.positionMin"));
      valid = false;
    }
  }
  return valid;
};

const load = async () => {
  try {
    const [groups, data] = await Promise.all([superCategoryApi.list(), categoryApi.list()]);
    superCategoryOptions.value = Array.isArray(groups) ? groups : [];
    const rows = Array.isArray(data) && data.length ? data.map(normalizeCategory) : [];
    categories.splice(0, categories.length, ...rows);
  } catch {
    superCategoryOptions.value = [];
    categories.splice(0, categories.length);
    status.value = t("common.loadFailed");
  }
  syncActiveSuperCategory();
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
  quickCategory.super_category = String(activeSuperCategoryId.value || sortedSuperCategoryOptions.value[0]?.id || "");
  quickCategory.name = "";
  quickCategory.name_i18n = {};
  quickCategory.description = "";
  quickCategory.description_i18n = {};
  quickCategory.position = activeCategories.value.length;
  quickCategory.is_published = true;
  quickFieldLocales.name = defaultLocale.value;
  quickFieldLocales.description = defaultLocale.value;
  quickModalOpen.value = true;
};
const closeQuickModal = () => {
  quickModalOpen.value = false;
};

const quickAdd = () => {
  const name = String(quickCategory.name || "").trim();
  if (name.length < 2) {
    toast.show(t("stepCategories.nameMin"), "error");
    return;
  }
  if (!quickCategory.super_category) {
    toast.show(t("stepCategories.superCategoryRequired"), "error");
    return;
  }
  const allowedTranslationLocales = availableContentLocales.value.map((locale) => locale.code).filter((locale) => locale !== defaultLocale.value);
  categories.push(normalizeCategory({
    super_category: quickCategory.super_category,
    name,
    name_i18n: pickI18nMap(quickCategory.name_i18n, allowedTranslationLocales),
    description: String(quickCategory.description || "").trim(),
    description_i18n: pickI18nMap(quickCategory.description_i18n, allowedTranslationLocales),
    position: Number(quickCategory.position) || 0,
    is_published: quickCategory.is_published,
  }));
  activeSuperCategoryId.value = String(quickCategory.super_category);
  closeQuickModal();
};

const removeByLocalId = async (localId) => {
  const index = categories.findIndex((cat) => cat.local_id === localId);
  if (index < 0) return;
  const [cat] = categories.splice(index, 1);
  if (cat?.id) removedIds.value.push(cat.id);
  if (String(editorLocalId.value) === String(localId)) closeEditor();
  delete rowErrors[localId];
};

const mapServerErrorsToRow = (localId, fieldErrors = {}) => {
  Object.entries(fieldErrors).forEach(([field, message]) => setRowError(localId, field, message));
};

const saveAll = async () => {
  saving.value = true;
  status.value = "";
  if (!validateClient()) {
    status.value = t("stepCategories.fixValidation");
    saving.value = false;
    return;
  }
  try {
    const validCats = categories.filter((cat) => cat.name?.trim());
    const allowedTranslationLocales = availableContentLocales.value.map((locale) => locale.code).filter((locale) => locale !== defaultLocale.value);
    for (const cat of validCats) {
      try {
        const saved = await categoryApi.upsert({
          ...cat,
          super_category: Number(cat.super_category) || cat.super_category,
          position: Number(cat.position) || 0,
          name_i18n: pickI18nMap(cat.name_i18n, allowedTranslationLocales),
          description_i18n: pickI18nMap(cat.description_i18n, allowedTranslationLocales),
          image_url: "",
        });
        cat.id = saved.id;
        cat.slug = saved.slug;
      } catch (error) {
        mapServerErrorsToRow(cat.local_id, error?.fieldErrors || {});
        throw error;
      }
    }
    for (const id of removedIds.value) {
      await categoryApi.remove(id);
    }
    removedIds.value = [];
    status.value = t("common.saved");
    toast.show(t("stepCategories.savedToast"), "success");
    if (!props.standalone) emit("next");
  } catch (error) {
    status.value = t("common.saveFailed");
    globalError.value = error?.message || t("stepCategories.saveFailed");
    toast.show(globalError.value, "error");
  } finally {
    saving.value = false;
  }
};

onMounted(load);
</script>
