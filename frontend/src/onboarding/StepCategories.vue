<template>
  <div class="ui-panel space-y-4 p-5">
    <h2 class="text-xl font-semibold">{{ t("stepCategories.title") }}</h2>
    <p class="text-sm text-slate-400">{{ t("stepCategories.description") }}</p>

    <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-3">
      <p class="text-sm text-slate-200">{{ t("stepCategories.quickTemplates") }}</p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="pack in categoryTemplatePacks"
          :key="pack.id"
          type="button"
          class="rounded-full border px-3 py-1.5 text-xs transition-colors"
          :class="selectedTemplate === pack.id ? 'border-brand-secondary text-brand-secondary bg-brand-secondary/10' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
          @click="selectedTemplate = pack.id"
        >
          {{ pack.label }}
        </button>
      </div>
      <button class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-brand-secondary" type="button" @click="applyTemplate">
        {{ t("stepCategories.applyTemplate") }}
      </button>
    </div>

    <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-3">
      <p class="text-sm text-slate-200">{{ t("stepCategories.translationsTitle") }}</p>
      <p class="text-xs text-slate-400">
        {{ t("stepCategories.translationsHint", { count: maxTranslationLocales }) }}
      </p>
      <div v-if="maxTranslationLocales > 0" class="flex flex-wrap gap-2">
        <button
          v-for="locale in secondaryLocales"
          :key="locale.code"
          type="button"
          class="rounded-full border px-3 py-1.5 text-xs transition-colors"
          :class="selectedTranslationLocales.includes(locale.code) ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
          :disabled="!selectedTranslationLocales.includes(locale.code) && selectedTranslationLocales.length >= maxTranslationLocales"
          @click="toggleTranslationLocale(locale.code)"
        >
          {{ locale.nativeLabel }} ({{ locale.label }})
        </button>
      </div>
      <p v-else class="text-xs text-slate-500">{{ t("stepCategories.translationsUnavailable") }}</p>
    </div>

    <div class="space-y-3">
      <div v-for="(cat, idx) in categories" :key="cat.local_id" class="space-y-2 rounded-xl border border-slate-800 bg-slate-900/70 p-3">
        <div class="flex items-center gap-3">
          <input
            v-model="cat.name"
            class="flex-1 rounded-xl bg-slate-900 border px-3 py-2"
            :class="rowError(cat, 'name') ? 'border-red-400' : 'border-slate-700'"
            :placeholder="t('stepCategories.categoryNamePlaceholder')"
            @input="clearRowError(cat.local_id, 'name')"
          />
          <input
            v-model.number="cat.position"
            type="number"
            min="0"
            class="w-20 rounded-xl bg-slate-900 border px-3 py-2"
            :class="rowError(cat, 'position') ? 'border-red-400' : 'border-slate-700'"
            @input="clearRowError(cat.local_id, 'position')"
          />
          <button class="text-sm text-red-300" @click="remove(idx)">{{ t("stepCategories.remove") }}</button>
        </div>

        <textarea
          v-model="cat.description"
          rows="2"
          class="ui-textarea"
          :class="rowError(cat, 'description') ? 'border-red-400' : 'border-slate-700'"
          :placeholder="t('stepCategories.categoryDescriptionPlaceholder')"
          @input="clearRowError(cat.local_id, 'description')"
        ></textarea>

        <div v-if="selectedTranslationLocales.length" class="space-y-2 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{{ t("stepCategories.translatedContent") }}</p>
          <div
            v-for="localeCode in selectedTranslationLocales"
            :key="`${cat.local_id}-${localeCode}`"
            class="grid gap-2 sm:grid-cols-2"
          >
            <input
              v-model="cat.name_i18n[localeCode]"
              class="ui-input"
              :placeholder="t('stepCategories.translatedNamePlaceholder', { locale: localeLabel(localeCode) })"
            />
            <input
              v-model="cat.description_i18n[localeCode]"
              class="ui-input"
              :placeholder="t('stepCategories.translatedDescriptionPlaceholder', { locale: localeLabel(localeCode) })"
            />
          </div>
        </div>

        <div
          class="rounded-xl border border-dashed p-3 space-y-2 transition-colors"
          :class="draggingRows[cat.local_id] ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
          @dragenter="setDragState(cat.local_id, true)"
          @dragleave="setDragState(cat.local_id, false)"
          @dragover="preventDropDefaults"
          @drop="dropImage(cat, $event)"
        >
          <div class="flex flex-wrap items-center gap-3">
            <input
              v-model="cat.image_url"
              class="flex-1 rounded-xl bg-slate-900 border px-3 py-2 text-sm"
              :class="rowError(cat, 'image_url') ? 'border-red-400' : 'border-slate-700'"
              :placeholder="t('stepCategories.categoryImageUrlPlaceholder')"
              @input="clearRowError(cat.local_id, 'image_url')"
            />
            <label class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 cursor-pointer hover:border-brand-secondary">
              {{ uploadingRows[cat.local_id] ? t("stepCategories.uploadingProgress", { progress: uploadProgressRows[cat.local_id] || 0 }) : t("stepCategories.uploadImage") }}
              <input type="file" accept="image/*" class="hidden" :disabled="uploadingRows[cat.local_id]" @change="uploadImage(cat, $event)" />
            </label>
            <button
              v-if="cat.image_url"
              type="button"
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-red-400 hover:text-red-300"
              @click="clearImage(cat)"
            >
              {{ t("stepCategories.removeImage") }}
            </button>
            <img v-if="cat.image_url" :src="cat.image_url" alt="" class="h-10 w-10 rounded-lg object-cover border border-slate-700" />
          </div>
          <p class="text-xs text-slate-500">{{ t("stepCategories.dropImageHint") }}</p>
        </div>
        <p class="text-xs text-slate-500">{{ t("stepCategories.acceptedFormats") }}</p>

        <div v-if="uploadingRows[cat.local_id]" class="h-1.5 w-full rounded bg-slate-800 overflow-hidden">
          <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${uploadProgressRows[cat.local_id] || 0}%` }"></div>
        </div>

        <p v-if="rowError(cat, 'name')" class="text-xs text-red-300">{{ rowError(cat, "name") }}</p>
        <p v-if="rowError(cat, 'description')" class="text-xs text-red-300">{{ rowError(cat, "description") }}</p>
        <p v-if="rowError(cat, 'position')" class="text-xs text-red-300">{{ rowError(cat, "position") }}</p>
        <p v-if="rowError(cat, 'image_url')" class="text-xs text-red-300">{{ rowError(cat, "image_url") }}</p>
        <p v-if="rowError(cat, 'slug')" class="text-xs text-red-300">{{ rowError(cat, "slug") }}</p>
        <p v-if="rowError(cat, 'non_field_errors')" class="text-xs text-red-300">{{ rowError(cat, "non_field_errors") }}</p>
      </div>
      <button class="text-sm text-[var(--color-secondary)]" @click="add">{{ t("stepCategories.addCategory") }}</button>
    </div>

    <p v-if="globalError" class="text-sm text-red-300">{{ globalError }}</p>

    <div class="flex flex-wrap items-center gap-3">
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
import { CATEGORY_TEMPLATE_PACKS } from "./starterTemplates";
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
const categoryTemplatePacks = CATEGORY_TEMPLATE_PACKS;
const selectedTemplate = ref(categoryTemplatePacks[0]?.id || "restaurant");
const selectedTranslationLocales = ref([]);

const hasActiveUploads = computed(() => Object.values(uploadingRows).some(Boolean));
const maxTranslationLocales = computed(() =>
  Math.max(0, Number(tenant.entitlements?.max_languages || 1) - 1)
);
const defaultLocale = computed(() => normalizeLocale(tenant.resolvedMeta?.profile?.language || "en"));
const secondaryLocales = computed(() => LOCALE_OPTIONS.filter((option) => option.code !== defaultLocale.value));

const localeLabel = (code) => {
  const match = LOCALE_OPTIONS.find((option) => option.code === code);
  return match ? `${match.nativeLabel}` : String(code || "").toUpperCase();
};

const enforceTranslationLocaleSelection = () => {
  const allowed = new Set(secondaryLocales.value.map((item) => item.code));
  let next = selectedTranslationLocales.value.filter((code) => allowed.has(code));
  if (next.length > maxTranslationLocales.value) {
    next = next.slice(0, maxTranslationLocales.value);
  }
  if (!next.length && maxTranslationLocales.value > 0) {
    next = secondaryLocales.value.slice(0, maxTranslationLocales.value).map((item) => item.code);
  }
  selectedTranslationLocales.value = next;
};

watch([secondaryLocales, maxTranslationLocales], enforceTranslationLocaleSelection, { immediate: true });

const hydrateTranslationLocalesFromRows = (rows = []) => {
  const allowed = new Set(secondaryLocales.value.map((item) => item.code));
  const discovered = [];
  rows.forEach((row) => {
    const maps = [row?.name_i18n, row?.description_i18n];
    maps.forEach((entry) => {
      if (!entry || typeof entry !== "object") return;
      Object.keys(entry).forEach((raw) => {
        const locale = String(raw || "").trim().toLowerCase();
        if (!locale || !allowed.has(locale)) return;
        if (!discovered.includes(locale)) discovered.push(locale);
      });
    });
  });
  if (!discovered.length) {
    enforceTranslationLocaleSelection();
    return;
  }
  const merged = [...selectedTranslationLocales.value, ...discovered].filter(
    (locale, index, source) => source.indexOf(locale) === index
  );
  selectedTranslationLocales.value = merged.slice(0, maxTranslationLocales.value);
  if (!selectedTranslationLocales.value.length) enforceTranslationLocaleSelection();
};

const toggleTranslationLocale = (code) => {
  const idx = selectedTranslationLocales.value.indexOf(code);
  if (idx >= 0) {
    selectedTranslationLocales.value.splice(idx, 1);
    return;
  }
  if (selectedTranslationLocales.value.length >= maxTranslationLocales.value) return;
  selectedTranslationLocales.value.push(code);
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

const pickI18nMap = (input) => {
  const out = {};
  if (!input || typeof input !== "object") return out;
  Object.entries(input).forEach(([rawLocale, rawValue]) => {
    const locale = String(rawLocale || "").trim().toLowerCase();
    const value = String(rawValue || "").trim();
    if (!locale) return;
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
    hydrateTranslationLocalesFromRows(rows);
  } catch {
    status.value = t("common.loadFailed");
    categories.splice(0, categories.length, normalize());
    enforceTranslationLocaleSelection();
  }
};

const applyTemplate = () => {
  const pack = categoryTemplatePacks.find((item) => item.id === selectedTemplate.value);
  if (!pack) return;

  const hasExisting = categories.some((cat) => (cat.name || "").trim() || cat.id);
  if (hasExisting) {
    const confirmed = window.confirm(t("stepCategories.confirmReplace"));
    if (!confirmed) return;
  }

  for (const cat of categories) {
    if (cat?.id) removedIds.value.push(cat.id);
    queueCleanup(cat?.image_url || "");
    delete rowErrors[cat?.local_id];
    delete uploadingRows[cat?.local_id];
    delete uploadProgressRows[cat?.local_id];
    delete draggingRows[cat?.local_id];
  }

  const next = pack.categories.map((name, idx) => normalize({ name, position: idx }));
  categories.splice(0, categories.length, ...next);
  clearAllErrors();
  status.value = t("stepCategories.templateApplied");
  toast.show(t("stepCategories.templateAppliedWithName", { name: pack.label }), "success");
};

const add = () => categories.push(normalize());

const remove = async (idx) => {
  const [cat] = categories.splice(idx, 1);
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
    for (const cat of validCats) {
      try {
        const saved = await categoryApi.upsert({
          ...cat,
          position: Number(cat.position) || 0,
          name_i18n: pickI18nMap(cat.name_i18n),
          description_i18n: pickI18nMap(cat.description_i18n),
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
