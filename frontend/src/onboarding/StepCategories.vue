<template>
  <div class="ui-panel space-y-5 p-5">
    <section class="ui-section-band space-y-4 rounded-[26px] p-4 sm:p-5">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("stepCategories.title") }}</p>
          <h2 class="text-xl font-semibold text-white sm:text-2xl">{{ t("stepCategories.description") }}</h2>
        </div>
        <button class="ui-btn-primary px-4 py-2 text-sm" type="button" @click="openQuickCategoryModal">
          {{ t("stepCategories.addCategory") }}
        </button>
      </div>
      <div class="flex flex-wrap gap-2">
        <span class="ui-data-strip">{{ categories.length }} {{ t("common.categories") }}</span>
        <span class="ui-data-strip">{{ availableContentLocales.length }} {{ t("stepCategories.translationsTitle") }}</span>
      </div>
    </section>

    <div class="space-y-3">
      <article
        v-for="(cat, idx) in categories"
        :key="cat.local_id"
        class="rounded-2xl border border-slate-800 bg-slate-950/75 p-4 shadow-[0_12px_28px_rgba(2,8,23,0.18)]"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <p class="text-[11px] uppercase tracking-[0.2em] text-slate-500">{{ t("common.categories") }} {{ idx + 1 }}</p>
            <h3 class="mt-1 truncate text-base font-semibold text-white">{{ cat.name || t("stepCategories.categoryNamePlaceholder") }}</h3>
            <p class="mt-1 line-clamp-2 text-sm text-slate-400">{{ cat.description || t("stepCategories.categoryDescriptionPlaceholder") }}</p>
            <div class="mt-2 flex flex-wrap gap-2">
              <span class="ui-data-strip">Pos: {{ Number(cat.position || 0) }}</span>
              <span class="ui-data-strip">{{ t("stepCategories.translationsTitle") }}: {{ Object.keys(cat.name_i18n || {}).length }}</span>
            </div>
          </div>
          <img
            v-if="cat.image_url"
            :src="cat.image_url"
            alt=""
            class="h-14 w-14 rounded-xl border border-slate-700 object-cover"
          />
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <button class="ui-btn-outline px-3 py-1.5 text-xs" type="button" @click="openCategoryEditor(cat.local_id)">
            Edit
          </button>
          <button class="rounded-full border border-red-400/25 px-3 py-1.5 text-xs text-red-200 hover:border-red-400/50" type="button" @click="remove(idx)">
            {{ t("stepCategories.remove") }}
          </button>
        </div>
      </article>
      <button class="ui-btn-outline px-4 py-2 text-sm" @click="openQuickCategoryModal">{{ t("stepCategories.addCategory") }}</button>
    </div>

    <Teleport to="body">
      <div
        v-if="categoryEditorModalOpen && editingCategory"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        @click.self="closeCategoryEditor"
      >
        <div class="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 p-4 shadow-2xl sm:p-5 space-y-4">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">Edit {{ t("common.categories") }}</h3>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeCategoryEditor">{{ t("common.close") }}</button>
          </div>

          <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr),110px]">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-xs text-slate-400">{{ t("stepCategories.categoryNamePlaceholder") }}</p>
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="locale in availableContentLocales"
                    :key="`cat-name-${locale.code}`"
                    type="button"
                    class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                    :class="categoryFieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                    @click="categoryFieldLocales.name = locale.code"
                  >
                    {{ locale.nativeLabel }}
                  </button>
                </div>
              </div>
              <input
                :value="localizedCategoryFieldValue(editingCategory, 'name', categoryFieldLocales.name)"
                class="ui-input"
                :class="rowError(editingCategory, 'name') ? 'border-red-400' : 'border-slate-700'"
                :placeholder="t('stepCategories.categoryNamePlaceholder')"
                @input="setLocalizedCategoryFieldValue(editingCategory, 'name', categoryFieldLocales.name, $event.target.value)"
              />
              <p v-if="rowError(editingCategory, 'name')" class="text-xs text-red-300">{{ rowError(editingCategory, "name") }}</p>
            </div>
            <div class="space-y-1">
              <input
                v-model.number="editingCategory.position"
                type="number"
                min="0"
                class="ui-input"
                :class="rowError(editingCategory, 'position') ? 'border-red-400' : 'border-slate-700'"
                @input="clearRowError(editingCategory.local_id, 'position')"
              />
              <p v-if="rowError(editingCategory, 'position')" class="text-xs text-red-300">{{ rowError(editingCategory, "position") }}</p>
            </div>
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
                  :class="categoryFieldLocales.description === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                  @click="categoryFieldLocales.description = locale.code"
                >
                  {{ locale.nativeLabel }}
                </button>
              </div>
            </div>
            <textarea
              :value="localizedCategoryFieldValue(editingCategory, 'description', categoryFieldLocales.description)"
              rows="2"
              class="ui-textarea"
              :class="rowError(editingCategory, 'description') ? 'border-red-400' : 'border-slate-700'"
              :placeholder="t('stepCategories.categoryDescriptionPlaceholder')"
              @input="setLocalizedCategoryFieldValue(editingCategory, 'description', categoryFieldLocales.description, $event.target.value)"
            ></textarea>
          </div>
          <p v-if="rowError(editingCategory, 'description')" class="text-xs text-red-300">{{ rowError(editingCategory, "description") }}</p>

          <div
            class="rounded-xl border border-dashed p-3 space-y-2 transition-colors"
            :class="draggingRows[editingCategory.local_id] ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
            @dragenter="setDragState(editingCategory.local_id, true)"
            @dragleave="setDragState(editingCategory.local_id, false)"
            @dragover="preventDropDefaults"
            @drop="dropImage(editingCategory, $event)"
          >
            <div class="flex flex-wrap items-center gap-3">
              <label class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 cursor-pointer hover:border-brand-secondary">
                {{ uploadingRows[editingCategory.local_id] ? t("stepCategories.uploadingProgress", { progress: uploadProgressRows[editingCategory.local_id] || 0 }) : t("stepCategories.uploadImage") }}
                <input type="file" accept="image/*" class="hidden" :disabled="uploadingRows[editingCategory.local_id]" @change="uploadImage(editingCategory, $event)" />
              </label>
              <button
                v-if="editingCategory.image_url"
                type="button"
                class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-red-400 hover:text-red-300"
                @click="clearImage(editingCategory)"
              >
                {{ t("stepCategories.removeImage") }}
              </button>
              <img v-if="editingCategory.image_url" :src="editingCategory.image_url" alt="" class="h-10 w-10 rounded-lg object-cover border border-slate-700" />
            </div>
            <p class="text-xs text-slate-500">{{ t("stepCategories.dropImageHint") }}</p>
          </div>
          <p class="text-xs text-slate-500">{{ t("stepCategories.acceptedFormats") }}</p>

          <div v-if="uploadingRows[editingCategory.local_id]" class="h-1.5 w-full rounded bg-slate-800 overflow-hidden">
            <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${uploadProgressRows[editingCategory.local_id] || 0}%` }"></div>
          </div>

          <p v-if="rowError(editingCategory, 'image_url')" class="text-xs text-red-300">{{ rowError(editingCategory, "image_url") }}</p>
          <p v-if="rowError(editingCategory, 'slug')" class="text-xs text-red-300">{{ rowError(editingCategory, "slug") }}</p>
          <p v-if="rowError(editingCategory, 'non_field_errors')" class="text-xs text-red-300">{{ rowError(editingCategory, "non_field_errors") }}</p>

          <div class="flex justify-end">
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="closeCategoryEditor">Done</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="quickCategoryModalOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
        @click.self="closeQuickCategoryModal"
      >
        <div class="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-950 p-4 shadow-2xl">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">{{ t("stepCategories.addCategory") }}</h3>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeQuickCategoryModal">{{ t("common.close") }}</button>
          </div>
          <div class="mt-4 space-y-3">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-xs text-slate-400">{{ t("stepCategories.categoryNamePlaceholder") }}</p>
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="locale in availableContentLocales"
                    :key="`quick-cat-name-${locale.code}`"
                    type="button"
                    class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                    :class="quickCategoryFieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                    @click="quickCategoryFieldLocales.name = locale.code"
                  >
                    {{ locale.nativeLabel }}
                  </button>
                </div>
              </div>
              <input
                :value="localizedQuickCategoryFieldValue('name', quickCategoryFieldLocales.name)"
                class="ui-input"
                :placeholder="t('stepCategories.categoryNamePlaceholder')"
                @input="setLocalizedQuickCategoryFieldValue('name', quickCategoryFieldLocales.name, $event.target.value)"
              />
            </div>

            <div class="space-y-1">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-xs text-slate-400">{{ t("stepCategories.categoryDescriptionPlaceholder") }}</p>
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="locale in availableContentLocales"
                    :key="`quick-cat-description-${locale.code}`"
                    type="button"
                    class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                    :class="quickCategoryFieldLocales.description === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                    @click="quickCategoryFieldLocales.description = locale.code"
                  >
                    {{ locale.nativeLabel }}
                  </button>
                </div>
              </div>
              <textarea
                :value="localizedQuickCategoryFieldValue('description', quickCategoryFieldLocales.description)"
                rows="2"
                class="ui-textarea"
                :placeholder="t('stepCategories.categoryDescriptionPlaceholder')"
                @input="setLocalizedQuickCategoryFieldValue('description', quickCategoryFieldLocales.description, $event.target.value)"
              ></textarea>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <input
                v-model.number="quickCategory.position"
                type="number"
                min="0"
                class="ui-input"
                :placeholder="t('stepCategories.positionMin')"
              />
              <div
                class="rounded-xl border border-dashed p-3 space-y-2 transition-colors"
                :class="draggingRows[quickCategory.local_id] ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
                @dragenter="setDragState(quickCategory.local_id, true)"
                @dragleave="setDragState(quickCategory.local_id, false)"
                @dragover="preventDropDefaults"
                @drop="dropImage(quickCategory, $event)"
              >
                <div class="flex flex-wrap items-center gap-3">
                  <label class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 cursor-pointer hover:border-brand-secondary">
                    {{ uploadingRows[quickCategory.local_id] ? t("stepCategories.uploadingProgress", { progress: uploadProgressRows[quickCategory.local_id] || 0 }) : t("stepCategories.uploadImage") }}
                    <input type="file" accept="image/*" class="hidden" :disabled="uploadingRows[quickCategory.local_id]" @change="uploadImage(quickCategory, $event)" />
                  </label>
                  <button
                    v-if="quickCategory.image_url"
                    type="button"
                    class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-red-400 hover:text-red-300"
                    @click="clearImage(quickCategory)"
                  >
                    {{ t("stepCategories.removeImage") }}
                  </button>
                  <img v-if="quickCategory.image_url" :src="quickCategory.image_url" alt="" class="h-10 w-10 rounded-lg object-cover border border-slate-700" />
                </div>
                <p class="text-xs text-slate-500">{{ t("stepCategories.dropImageHint") }}</p>
              </div>
            </div>
            <p class="text-xs text-slate-500">{{ t("stepCategories.acceptedFormats") }}</p>
            <div v-if="uploadingRows[quickCategory.local_id]" class="h-1.5 w-full rounded bg-slate-800 overflow-hidden">
              <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${uploadProgressRows[quickCategory.local_id] || 0}%` }"></div>
            </div>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button type="button" class="ui-btn-outline px-4 py-2 text-sm" @click="closeQuickCategoryModal">{{ t("common.close") }}</button>
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="quickAddCategory">{{ t("stepCategories.addCategory") }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <p v-if="globalError" class="text-sm text-red-300">{{ globalError }}</p>

    <div class="flex flex-wrap items-center gap-3 border-t border-slate-800/80 pt-3">
      <button class="ui-btn-primary px-4 py-2" :disabled="saving || hasActiveUploads" @click="saveAndNext">
        {{ saving ? t("common.saving") : t("common.saveAndNext") }}
      </button>
      <button class="ui-btn-outline px-4 py-2" @click="$emit('back')">{{ t("common.previous") }}</button>
      <p class="text-sm text-slate-400">{{ status }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { categoryApi, uploadApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { LOCALE_OPTIONS, normalizeLocale } from "../i18n/config";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const categories = reactive([]);
const removedIds = ref([]);
const rowErrors = reactive({});
const uploadingRows = reactive({});
const uploadProgressRows = reactive({});
const draggingRows = reactive({});
const pendingCleanup = ref([]);
const globalError = ref("");
const saving = ref(false);
const status = ref("");
const toast = useToastStore();
const tenant = useTenantStore();
const { t } = useI18n();
const emit = defineEmits(["next", "back"]);
const quickCategoryModalOpen = ref(false);
const categoryEditorModalOpen = ref(false);
const categoryEditorLocalId = ref("");
const categoryFieldLocales = reactive({
  name: "en",
  description: "en",
});
const quickCategory = reactive({
  local_id: "quick-category",
  name: "",
  name_i18n: {},
  description: "",
  description_i18n: {},
  position: 0,
  image_url: "",
});
const quickCategoryFieldLocales = reactive({
  name: "en",
  description: "en",
});
const editingCategory = computed(
  () => categories.find((cat) => String(cat.local_id) === String(categoryEditorLocalId.value)) || null
);

const hasActiveUploads = computed(() => Object.values(uploadingRows).some(Boolean));
const maxTranslationLocales = computed(() =>
  Math.max(0, Number(tenant.entitlements?.max_languages || 1) - 1)
);
const defaultLocale = computed(() => normalizeLocale(tenant.resolvedMeta?.profile?.language || "en"));
const availableContentLocales = computed(() => {
  const primary = LOCALE_OPTIONS.find((option) => option.code === defaultLocale.value) || LOCALE_OPTIONS[0];
  const secondary = LOCALE_OPTIONS.filter((option) => option.code !== primary.code).slice(0, maxTranslationLocales.value);
  return [primary, ...secondary];
});

const syncCategoryFieldLocales = () => {
  const allowed = new Set(availableContentLocales.value.map((locale) => locale.code));
  if (!allowed.has(categoryFieldLocales.name)) categoryFieldLocales.name = defaultLocale.value;
  if (!allowed.has(categoryFieldLocales.description)) categoryFieldLocales.description = defaultLocale.value;
  if (!allowed.has(quickCategoryFieldLocales.name)) quickCategoryFieldLocales.name = defaultLocale.value;
  if (!allowed.has(quickCategoryFieldLocales.description)) quickCategoryFieldLocales.description = defaultLocale.value;
};

watch([availableContentLocales, defaultLocale], syncCategoryFieldLocales, { immediate: true });

const localizedCategoryFieldValue = (cat, field, localeCode) => {
  if (!cat) return "";
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(cat[field] || "");
  const map = cat[`${field}_i18n`];
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};

const setLocalizedCategoryFieldValue = (cat, field, localeCode, value) => {
  if (!cat) return;
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    cat[field] = nextValue;
  } else {
    const mapField = `${field}_i18n`;
    if (!cat[mapField] || typeof cat[mapField] !== "object") cat[mapField] = {};
    if (nextValue.trim()) {
      cat[mapField][locale] = nextValue;
    } else {
      delete cat[mapField][locale];
    }
  }
  clearRowError(cat.local_id, field);
};

const localizedQuickCategoryFieldValue = (field, localeCode) => {
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(quickCategory[field] || "");
  const map = quickCategory[`${field}_i18n`];
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};

const setLocalizedQuickCategoryFieldValue = (field, localeCode, value) => {
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    quickCategory[field] = nextValue;
  } else {
    const mapField = `${field}_i18n`;
    if (!quickCategory[mapField] || typeof quickCategory[mapField] !== "object") quickCategory[mapField] = {};
    if (nextValue.trim()) {
      quickCategory[mapField][locale] = nextValue;
    } else {
      delete quickCategory[mapField][locale];
    }
  }
};
const isManagedUpload = (value = "") => /\/uploads\//.test(String(value));
const cleanupManagedUpload = async (value) => {
  if (!isManagedUpload(value)) return;
  try {
    await uploadApi.removeImage(value);
  } catch {
    // Non-blocking cleanup.
  }
};

const queueCleanup = (value) => {
  if (!isManagedUpload(value)) return;
  if (pendingCleanup.value.includes(value)) return;
  pendingCleanup.value.push(value);
};

const flushPendingCleanup = async () => {
  if (!pendingCleanup.value.length) return;
  const stillReferenced = new Set(categories.map((cat) => cat.image_url).filter(Boolean));
  const queue = [...pendingCleanup.value];
  pendingCleanup.value = [];
  for (const value of queue) {
    if (stillReferenced.has(value)) continue;
    await cleanupManagedUpload(value);
  }
};

const preventDropDefaults = (event) => {
  event.preventDefault();
  event.stopPropagation();
};

const setDragState = (localId, active) => {
  draggingRows[localId] = active;
};

const fileFromEvent = (event) => {
  if (!event) return null;
  if (event.dataTransfer?.files?.length) return event.dataTransfer.files[0];
  if (event.target?.files?.length) return event.target.files[0];
  return null;
};

const normalize = (cat = {}) => ({
  id: cat.id,
  local_id: cat.id || crypto.randomUUID(),
  name: cat.name || "",
  name_i18n: cat.name_i18n && typeof cat.name_i18n === "object" ? { ...cat.name_i18n } : {},
  slug: cat.slug || "",
  description: cat.description || "",
  description_i18n: cat.description_i18n && typeof cat.description_i18n === "object" ? { ...cat.description_i18n } : {},
  image_url: cat.image_url || "",
  position: cat.position ?? categories.length,
  is_published: cat.is_published ?? true,
});

const pickI18nMap = (input, allowedLocales = null) => {
  const out = {};
  if (!input || typeof input !== "object") return out;
  const allowed = Array.isArray(allowedLocales)
    ? new Set(allowedLocales.map((locale) => String(locale || "").trim().toLowerCase()))
    : null;
  Object.entries(input).forEach(([rawLocale, rawValue]) => {
    const locale = String(rawLocale || "").trim().toLowerCase();
    const value = String(rawValue || "").trim();
    if (!locale) return;
    if (allowed && !allowed.has(locale)) return;
    if (value) out[locale] = value;
  });
  return out;
};

const clearAllErrors = () => {
  Object.keys(rowErrors).forEach((key) => delete rowErrors[key]);
  globalError.value = "";
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

const validateClient = () => {
  clearAllErrors();
  const filled = categories.filter((c) => c.name?.trim());
  if (!filled.length) {
    globalError.value = t("stepCategories.addAtLeastOne");
    return false;
  }

  const names = new Map();
  let valid = true;
  for (const cat of filled) {
    const name = cat.name.trim();
    if (name.length < 2) {
      setRowError(cat.local_id, "name", t("stepCategories.nameMin"));
      valid = false;
    }
    const key = name.toLowerCase();
    if (names.has(key)) {
      setRowError(cat.local_id, "name", t("stepCategories.duplicateName"));
      setRowError(names.get(key), "name", t("stepCategories.duplicateName"));
      valid = false;
    } else {
      names.set(key, cat.local_id);
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
    const data = await categoryApi.list();
    const rows = data.length ? data.map(normalize) : [normalize()];
    categories.splice(0, categories.length, ...rows);
  } catch {
    status.value = t("common.loadFailed");
    categories.splice(0, categories.length, normalize());
  }
};

const openCategoryEditor = (localId) => {
  categoryEditorLocalId.value = String(localId || "");
  categoryEditorModalOpen.value = true;
};

const closeCategoryEditor = () => {
  categoryEditorModalOpen.value = false;
  categoryEditorLocalId.value = "";
};

const openQuickCategoryModal = () => {
  quickCategory.name = "";
  quickCategory.name_i18n = {};
  quickCategory.description = "";
  quickCategory.description_i18n = {};
  quickCategory.position = categories.length;
  quickCategory.image_url = "";
  uploadingRows[quickCategory.local_id] = false;
  uploadProgressRows[quickCategory.local_id] = 0;
  draggingRows[quickCategory.local_id] = false;
  quickCategoryFieldLocales.name = defaultLocale.value;
  quickCategoryFieldLocales.description = defaultLocale.value;
  quickCategoryModalOpen.value = true;
};

const closeQuickCategoryModal = () => {
  if (quickCategory.image_url && isManagedUpload(quickCategory.image_url)) {
    cleanupManagedUpload(quickCategory.image_url);
    quickCategory.image_url = "";
  }
  quickCategoryModalOpen.value = false;
};

const quickAddCategory = () => {
  const name = String(quickCategory.name || "").trim();
  if (name.length < 2) {
    toast.show(t("stepCategories.nameMin"), "error");
    return;
  }
  categories.push(
    normalize({
      name,
      name_i18n: pickI18nMap(
        quickCategory.name_i18n,
        availableContentLocales.value
          .map((locale) => locale.code)
          .filter((locale) => locale !== defaultLocale.value)
      ),
      description: String(quickCategory.description || "").trim(),
      description_i18n: pickI18nMap(
        quickCategory.description_i18n,
        availableContentLocales.value
          .map((locale) => locale.code)
          .filter((locale) => locale !== defaultLocale.value)
      ),
      position: Number(quickCategory.position) || 0,
      image_url: String(quickCategory.image_url || "").trim(),
    })
  );
  quickCategoryModalOpen.value = false;
};

const remove = async (idx) => {
  const [cat] = categories.splice(idx, 1);
  if (String(categoryEditorLocalId.value) === String(cat?.local_id || "")) {
    closeCategoryEditor();
  }
  if (cat?.id) removedIds.value.push(cat.id);
  delete rowErrors[cat?.local_id];
  delete uploadingRows[cat?.local_id];
  delete uploadProgressRows[cat?.local_id];
  delete draggingRows[cat?.local_id];
  queueCleanup(cat?.image_url || "");
  if (!categories.length) categories.push(normalize());
};

const clearImage = async (cat) => {
  const old = cat.image_url;
  cat.image_url = "";
  queueCleanup(old);
};

const mapServerErrorsToRow = (localId, fieldErrors = {}) => {
  Object.entries(fieldErrors).forEach(([field, message]) => {
    setRowError(localId, field, message);
  });
};

const uploadImageFile = async (cat, file) => {
  if (!file) return;
  uploadingRows[cat.local_id] = true;
  uploadProgressRows[cat.local_id] = 0;
  clearRowError(cat.local_id, "image_url");
  const old = cat.image_url;
  try {
    const result = await uploadApi.image(file, {
      variant: "category",
      onProgress: (pct) => {
        uploadProgressRows[cat.local_id] = pct;
      },
    });
    cat.image_url = result.url || "";
    queueCleanup(old);
    toast.show(t("stepCategories.imageUploaded"), "success");
  } catch (e) {
    mapServerErrorsToRow(cat.local_id, e?.fieldErrors || {});
    globalError.value = e?.message || t("stepCategories.imageUploadFailed");
    toast.show(globalError.value, "error");
  } finally {
    uploadingRows[cat.local_id] = false;
    setDragState(cat.local_id, false);
  }
};

const uploadImage = async (cat, event) => {
  const file = fileFromEvent(event);
  if (event?.target) event.target.value = "";
  await uploadImageFile(cat, file);
};

const dropImage = async (cat, event) => {
  preventDropDefaults(event);
  setDragState(cat.local_id, false);
  await uploadImageFile(cat, fileFromEvent(event));
};

const saveAndNext = async () => {
  saving.value = true;
  status.value = "";

  if (!validateClient()) {
    status.value = t("stepCategories.fixValidation");
    saving.value = false;
    return;
  }

  try {
    const validCats = categories.filter((c) => c.name?.trim());
    const allowedTranslationLocales = availableContentLocales.value
      .map((locale) => locale.code)
      .filter((locale) => locale !== defaultLocale.value);
    for (const cat of validCats) {
      try {
        const saved = await categoryApi.upsert({
          ...cat,
          position: Number(cat.position) || 0,
          name_i18n: pickI18nMap(cat.name_i18n, allowedTranslationLocales),
          description_i18n: pickI18nMap(cat.description_i18n, allowedTranslationLocales),
        });
        cat.id = saved.id;
        cat.slug = saved.slug;
      } catch (e) {
        mapServerErrorsToRow(cat.local_id, e?.fieldErrors || {});
        throw e;
      }
    }
    for (const id of removedIds.value) {
      await categoryApi.remove(id);
    }
    await flushPendingCleanup();
    removedIds.value = [];
    status.value = t("common.saved");
    toast.show(t("stepCategories.savedToast"), "success");
    emit("next");
  } catch (e) {
    status.value = t("common.saveFailed");
    globalError.value = e?.message || t("stepCategories.saveFailed");
    toast.show(globalError.value, "error");
  } finally {
    saving.value = false;
  }
};

onMounted(load);
</script>
