<template>
  <div class="ui-panel space-y-4 p-5">
    <h2 class="text-xl font-semibold">{{ t("stepDishes.title") }}</h2>
    <p class="text-sm text-slate-400">{{ t("stepDishes.description") }}</p>

    <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
      <p class="text-sm text-slate-200">{{ t("stepDishes.quickStarters") }}</p>
      <button
        type="button"
        class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-brand-secondary"
        @click="addStarterDishes"
      >
        {{ t("stepDishes.addSuggested") }}
      </button>
      <p class="text-xs text-slate-500">{{ t("stepDishes.quickStarterHint") }}</p>
    </div>

    <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-3">
      <p class="text-sm text-slate-200">{{ t("stepDishes.translationsTitle") }}</p>
      <p class="text-xs text-slate-400">
        {{ t("stepDishes.translationsHint", { count: maxTranslationLocales }) }}
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
      <p v-else class="text-xs text-slate-500">{{ t("stepDishes.translationsUnavailable") }}</p>
    </div>

    <div class="space-y-3">
      <div v-for="(dish, idx) in dishes" :key="dish.local_id" class="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-2">
        <div class="grid gap-3 sm:grid-cols-2">
          <div class="space-y-1">
            <input
              v-model="dish.name"
              class="ui-input"
              :class="rowError(dish, 'name') ? 'border-red-400' : 'border-slate-700'"
              :placeholder="t('stepDishes.dishNamePlaceholder')"
              @input="clearRowError(dish.local_id, 'name')"
            />
            <p v-if="rowError(dish, 'name')" class="text-xs text-red-300">{{ rowError(dish, "name") }}</p>
          </div>

          <div class="space-y-1">
            <select
              v-model="dish.category"
              class="ui-input"
              :class="rowError(dish, 'category') ? 'border-red-400' : 'border-slate-700'"
              @change="clearRowError(dish.local_id, 'category')"
            >
              <option disabled value="">{{ t("stepDishes.selectCategory") }}</option>
              <option v-for="cat in categoryOptions" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
            </select>
            <p v-if="rowError(dish, 'category')" class="text-xs text-red-300">{{ rowError(dish, "category") }}</p>
          </div>

          <div class="space-y-1">
            <input
              v-model.number="dish.price"
              type="number"
              min="0"
              step="0.01"
              class="ui-input"
              :class="rowError(dish, 'price') ? 'border-red-400' : 'border-slate-700'"
              :placeholder="t('stepDishes.pricePlaceholder')"
              @input="clearRowError(dish.local_id, 'price')"
            />
            <p v-if="rowError(dish, 'price')" class="text-xs text-red-300">{{ rowError(dish, "price") }}</p>
          </div>

          <div class="space-y-1">
            <div
              class="rounded-xl border border-dashed p-3 space-y-2 transition-colors"
              :class="draggingRows[dish.local_id] ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
              @dragenter="setDragState(dish.local_id, true)"
              @dragleave="setDragState(dish.local_id, false)"
              @dragover="preventDropDefaults"
              @drop="dropImage(dish, $event)"
            >
              <input
                v-model="dish.image_url"
                class="ui-input"
                :class="rowError(dish, 'image_url') ? 'border-red-400' : 'border-slate-700'"
                :placeholder="t('stepDishes.imageUrlPlaceholder')"
                @input="clearRowError(dish.local_id, 'image_url')"
              />
              <p v-if="rowError(dish, 'image_url')" class="text-xs text-red-300">{{ rowError(dish, "image_url") }}</p>
              <div class="flex flex-wrap items-center gap-3">
                <label class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 cursor-pointer hover:border-brand-secondary">
                  {{ uploadingRows[dish.local_id] ? t("stepDishes.uploadingProgress", { progress: uploadProgressRows[dish.local_id] || 0 }) : t("stepDishes.uploadImage") }}
                  <input type="file" accept="image/*" class="hidden" :disabled="uploadingRows[dish.local_id]" @change="uploadImage(dish, $event)" />
                </label>
                <button
                  v-if="dish.image_url"
                  type="button"
                  class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-red-400 hover:text-red-300"
                  @click="clearImage(dish)"
                >
                  {{ t("stepDishes.removeImage") }}
                </button>
                <img v-if="dish.image_url" :src="dish.image_url" alt="" class="h-10 w-10 rounded-lg object-cover border border-slate-700" />
              </div>
              <p class="text-xs text-slate-500">{{ t("stepDishes.dropImageHint") }}</p>
            </div>

            <p class="text-xs text-slate-500">{{ t("stepDishes.acceptedFormats") }}</p>
            <div v-if="uploadingRows[dish.local_id]" class="h-1.5 w-full rounded bg-slate-800 overflow-hidden">
              <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${uploadProgressRows[dish.local_id] || 0}%` }"></div>
            </div>
          </div>
        </div>

        <textarea
          v-model="dish.description"
          rows="2"
          class="ui-textarea"
          :class="rowError(dish, 'description') ? 'border-red-400' : 'border-slate-700'"
          :placeholder="t('stepDishes.descriptionPlaceholder')"
          @input="clearRowError(dish.local_id, 'description')"
        ></textarea>
        <p v-if="rowError(dish, 'description')" class="text-xs text-red-300">{{ rowError(dish, "description") }}</p>

        <div v-if="selectedTranslationLocales.length" class="space-y-2 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{{ t("stepDishes.translatedContent") }}</p>
          <div
            v-for="localeCode in selectedTranslationLocales"
            :key="`${dish.local_id}-${localeCode}`"
            class="grid gap-2 sm:grid-cols-2"
          >
            <input
              v-model="dish.name_i18n[localeCode]"
              class="ui-input"
              :placeholder="t('stepDishes.translatedNamePlaceholder', { locale: localeLabel(localeCode) })"
            />
            <input
              v-model="dish.description_i18n[localeCode]"
              class="ui-input"
              :placeholder="t('stepDishes.translatedDescriptionPlaceholder', { locale: localeLabel(localeCode) })"
            />
          </div>
        </div>

        <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.variantsTitle") }}</p>
            <button
              type="button"
              class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-brand-secondary"
              @click="addOption(dish)"
            >
              {{ t("stepDishes.addVariant") }}
            </button>
          </div>
          <p class="text-xs text-slate-500">{{ t("stepDishes.variantsHint") }}</p>

          <div v-if="dish.options?.length" class="space-y-2">
            <div
              v-for="(option, optIdx) in dish.options"
              :key="option.local_id"
              class="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
            >
              <div class="grid gap-2 sm:grid-cols-[1fr,130px,130px,auto] sm:items-center">
                <input
                  v-model="option.name"
                  class="ui-input"
                  :class="rowError(dish, optionFieldKey(option, 'name')) ? 'border-red-400' : 'border-slate-700'"
                  :placeholder="t('stepDishes.variantNamePlaceholder')"
                  @input="clearRowError(dish.local_id, optionFieldKey(option, 'name'))"
                />
                <input
                  v-model.number="option.price_delta"
                  type="number"
                  min="0"
                  step="0.01"
                  class="ui-input"
                  :class="rowError(dish, optionFieldKey(option, 'price_delta')) ? 'border-red-400' : 'border-slate-700'"
                  :placeholder="t('stepDishes.extraPricePlaceholder')"
                  @input="clearRowError(dish.local_id, optionFieldKey(option, 'price_delta'))"
                />
                <input
                  v-model.number="option.max_select"
                  type="number"
                  min="1"
                  step="1"
                  class="ui-input"
                  :class="rowError(dish, optionFieldKey(option, 'max_select')) ? 'border-red-400' : 'border-slate-700'"
                  :placeholder="t('stepDishes.maxSelectPlaceholder')"
                  @input="clearRowError(dish.local_id, optionFieldKey(option, 'max_select'))"
                />
                <button
                  type="button"
                  class="rounded-full border border-slate-700 px-3 py-2 text-xs text-red-200 hover:border-red-400/60"
                  @click="removeOption(dish, optIdx)"
                >
                  {{ t("stepDishes.remove") }}
                </button>
              </div>
              <label class="mt-2 inline-flex items-center gap-2 text-xs text-slate-300">
                <input v-model="option.is_required" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
                {{ t("stepDishes.requiredBeforeAddToCart") }}
              </label>
              <div v-if="selectedTranslationLocales.length" class="mt-2 grid gap-2 sm:grid-cols-2">
                <input
                  v-for="localeCode in selectedTranslationLocales"
                  :key="`${option.local_id}-${localeCode}`"
                  v-model="option.name_i18n[localeCode]"
                  class="ui-input"
                  :placeholder="t('stepDishes.translatedVariantPlaceholder', { locale: localeLabel(localeCode) })"
                />
              </div>
              <p v-if="rowError(dish, optionFieldKey(option, 'name'))" class="mt-1 text-xs text-red-300">{{ rowError(dish, optionFieldKey(option, "name")) }}</p>
              <p v-if="rowError(dish, optionFieldKey(option, 'price_delta'))" class="mt-1 text-xs text-red-300">{{ rowError(dish, optionFieldKey(option, "price_delta")) }}</p>
              <p v-if="rowError(dish, optionFieldKey(option, 'max_select'))" class="mt-1 text-xs text-red-300">{{ rowError(dish, optionFieldKey(option, "max_select")) }}</p>
            </div>
          </div>
          <p v-else class="text-xs text-slate-500">{{ t("stepDishes.noVariants") }}</p>
          <p v-if="rowError(dish, 'options')" class="text-xs text-red-300">{{ rowError(dish, "options") }}</p>
        </div>

        <p v-if="rowError(dish, 'slug')" class="text-xs text-red-300">{{ rowError(dish, "slug") }}</p>
        <p v-if="rowError(dish, 'non_field_errors')" class="text-xs text-red-300">{{ rowError(dish, "non_field_errors") }}</p>
        <button class="text-xs text-red-300" @click="remove(idx)">{{ t("stepDishes.removeDish") }}</button>
      </div>
      <button class="text-sm text-[var(--color-secondary)]" @click="add">{{ t("stepDishes.addDish") }}</button>
    </div>

    <p v-if="globalError" class="text-sm text-red-300">{{ globalError }}</p>

    <div class="flex flex-wrap items-center gap-3">
      <button class="ui-btn-primary px-4 py-2" @click="saveAndNext" :disabled="saving || hasActiveUploads">
        {{ saving ? t("common.saving") : t("common.saveAndNext") }}
      </button>
      <button class="ui-btn-outline px-4 py-2" @click="$emit('back')">{{ t("common.previous") }}</button>
      <p class="text-sm text-slate-400">{{ status }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted, watch } from "vue";
import { categoryApi, dishApi, dishOptionApi, uploadApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { LOCALE_OPTIONS, normalizeLocale } from "../i18n/config";
import { suggestDishNameForCategory } from "./starterTemplates";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const dishes = reactive([]);
const categoryOptions = ref([]);
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
    const options = Array.isArray(row?.options) ? row.options : [];
    options.forEach((option) => {
      if (!option?.name_i18n || typeof option.name_i18n !== "object") return;
      Object.keys(option.name_i18n).forEach((raw) => {
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
  } catch (e) {
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
  const stillReferenced = new Set(dishes.map((dish) => dish.image_url).filter(Boolean));
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

const normalizeOption = (option = {}) => ({
  id: option.id,
  local_id: option.id ? `opt-${option.id}` : crypto.randomUUID(),
  name: option.name || "",
  name_i18n: option.name_i18n && typeof option.name_i18n === "object" ? { ...option.name_i18n } : {},
  price_delta: Number(option.price_delta || 0),
  is_required: option.is_required === true,
  max_select: Math.max(1, Number(option.max_select) || 1),
});

const normalize = (dish = {}) => ({
  id: dish.id,
  local_id: dish.id || crypto.randomUUID(),
  name: dish.name || "",
  name_i18n: dish.name_i18n && typeof dish.name_i18n === "object" ? { ...dish.name_i18n } : {},
  slug: dish.slug || "",
  category: dish.category || "",
  price: Number(dish.price || 0),
  currency: dish.currency || "USD",
  image_url: dish.image_url || "",
  description: dish.description || "",
  description_i18n: dish.description_i18n && typeof dish.description_i18n === "object" ? { ...dish.description_i18n } : {},
  position: dish.position ?? dishes.length,
  is_published: dish.is_published ?? true,
  options: Array.isArray(dish.options) ? dish.options.map((option) => normalizeOption(option)) : [],
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

const optionFieldKey = (option, field) => `option_${option?.local_id || "new"}_${field}`;

const addOption = (dish) => {
  if (!Array.isArray(dish.options)) dish.options = [];
  dish.options.push(normalizeOption());
};

const removeOption = (dish, optionIndex) => {
  if (!Array.isArray(dish.options)) return;
  const [option] = dish.options.splice(optionIndex, 1);
  if (!option) return;
  clearRowError(dish.local_id, optionFieldKey(option, "name"));
  clearRowError(dish.local_id, optionFieldKey(option, "price_delta"));
  clearRowError(dish.local_id, optionFieldKey(option, "max_select"));
  clearRowError(dish.local_id, "options");
};

const rowError = (dish, field) => rowErrors[dish.local_id]?.[field] || "";
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
  const filled = dishes.filter((d) => d.name?.trim());
  if (!filled.length) {
    globalError.value = t("stepDishes.addAtLeastOne");
    return false;
  }

  let valid = true;
  for (const dish of filled) {
    const name = dish.name.trim();
    if (name.length < 2) {
      setRowError(dish.local_id, "name", t("stepDishes.nameMin"));
      valid = false;
    }
    if (!dish.category) {
      setRowError(dish.local_id, "category", t("stepDishes.selectCategoryError"));
      valid = false;
    }
    if (Number(dish.price) < 0) {
      setRowError(dish.local_id, "price", t("stepDishes.priceMin"));
      valid = false;
    }

    const optionNames = new Set();
    const optionRows = Array.isArray(dish.options) ? dish.options : [];
    for (const option of optionRows) {
      const optionName = String(option?.name || "").trim();
      const hasAnyData =
        optionName.length > 0 ||
        Number(option?.price_delta || 0) !== 0 ||
        option?.is_required === true ||
        Number(option?.max_select || 1) !== 1;

      if (!hasAnyData) continue;

      if (!optionName) {
        setRowError(dish.local_id, optionFieldKey(option, "name"), t("stepDishes.variantNameRequired"));
        valid = false;
        continue;
      }

      const normalizedName = optionName.toLowerCase();
      if (optionNames.has(normalizedName)) {
        setRowError(dish.local_id, optionFieldKey(option, "name"), t("stepDishes.variantDuplicate"));
        valid = false;
      } else {
        optionNames.add(normalizedName);
      }

      if (Number(option.price_delta) < 0) {
        setRowError(dish.local_id, optionFieldKey(option, "price_delta"), t("stepDishes.extraPriceMin"));
        valid = false;
      }

      if (Number(option.max_select || 0) < 1) {
        setRowError(dish.local_id, optionFieldKey(option, "max_select"), t("stepDishes.maxSelectMin"));
        valid = false;
      }
    }
  }
  return valid;
};

const load = async () => {
  try {
    categoryOptions.value = await categoryApi.list();
  } catch (e) {
    categoryOptions.value = [];
  }
  try {
    const data = await dishApi.list();
    const rows = data.length ? data.map(normalize) : [normalize()];
    dishes.splice(0, dishes.length, ...rows);
    hydrateTranslationLocalesFromRows(rows);
  } catch (e) {
    status.value = t("common.loadFailed");
    dishes.splice(0, dishes.length, normalize());
    enforceTranslationLocaleSelection();
  }
};

const addStarterDishes = () => {
  if (!categoryOptions.value.length) {
    toast.show(t("stepDishes.addCategoriesFirst"), "error");
    return;
  }

  const categoryIdsWithDishes = new Set(
    dishes
      .filter((dish) => (dish.name || "").trim() && dish.category)
      .map((dish) => String(dish.category))
  );

  const starters = categoryOptions.value
    .filter((cat) => !categoryIdsWithDishes.has(String(cat.id)))
    .map((cat, idx) =>
      normalize({
        name: suggestDishNameForCategory(cat.name),
        category: cat.id,
        price: 9.9,
        description: t("stepDishes.starterDescription", { category: String(cat.name || "menu").toLowerCase() }),
        position: dishes.length + idx,
      })
    );

  if (!starters.length) {
    toast.show(t("stepDishes.eachCategoryHasDish"), "success");
    return;
  }

  dishes.push(...starters);
  status.value = t("stepDishes.startersAddedStatus");
  toast.show(t("stepDishes.startersAddedToast", { count: starters.length }), "success");
};

const add = () => dishes.push(normalize());

const remove = async (idx) => {
  const [dish] = dishes.splice(idx, 1);
  if (dish?.id) removedIds.value.push(dish.id);
  delete rowErrors[dish?.local_id];
  delete uploadingRows[dish?.local_id];
  delete uploadProgressRows[dish?.local_id];
  delete draggingRows[dish?.local_id];
  queueCleanup(dish?.image_url || "");
  if (!dishes.length) dishes.push(normalize());
};

const clearImage = async (dish) => {
  const old = dish.image_url;
  dish.image_url = "";
  queueCleanup(old);
};

const mapServerErrorsToRow = (localId, fieldErrors = {}) => {
  Object.entries(fieldErrors).forEach(([field, message]) => {
    setRowError(localId, field, message);
  });
};

const uploadImageFile = async (dish, file) => {
  if (!file) return;
  uploadingRows[dish.local_id] = true;
  uploadProgressRows[dish.local_id] = 0;
  clearRowError(dish.local_id, "image_url");
  const old = dish.image_url;
  try {
    const result = await uploadApi.image(file, {
      variant: "dish",
      onProgress: (pct) => {
        uploadProgressRows[dish.local_id] = pct;
      },
    });
    dish.image_url = result.url || "";
    queueCleanup(old);
    toast.show(t("stepDishes.imageUploaded"), "success");
  } catch (e) {
    mapServerErrorsToRow(dish.local_id, e?.fieldErrors || {});
    globalError.value = e?.message || t("stepDishes.imageUploadFailed");
    toast.show(globalError.value, "error");
  } finally {
    uploadingRows[dish.local_id] = false;
    setDragState(dish.local_id, false);
  }
};

const uploadImage = async (dish, event) => {
  const file = fileFromEvent(event);
  if (event?.target) event.target.value = "";
  await uploadImageFile(dish, file);
};

const dropImage = async (dish, event) => {
  preventDropDefaults(event);
  setDragState(dish.local_id, false);
  await uploadImageFile(dish, fileFromEvent(event));
};

const saveAndNext = async () => {
  saving.value = true;
  status.value = "";
  if (!validateClient()) {
    status.value = t("stepDishes.fixValidation");
    saving.value = false;
    return;
  }
  try {
    const validDishes = dishes.filter((d) => d.name?.trim() && d.category);
    for (const dish of validDishes) {
      try {
        const saved = await dishApi.upsert({
          ...dish,
          price: Number(dish.price) || 0,
          name_i18n: pickI18nMap(dish.name_i18n),
          description_i18n: pickI18nMap(dish.description_i18n),
        });
        dish.id = saved.id;
        dish.slug = saved.slug;
        const desiredOptions = Array.isArray(dish.options) ? dish.options : [];
        const savedOptions = await dishOptionApi.syncForDish(
          dish.id,
          desiredOptions.map((option) => ({
            ...option,
            name_i18n: pickI18nMap(option.name_i18n),
          }))
        );
        dish.options = savedOptions.map((option) => normalizeOption(option));
      } catch (e) {
        mapServerErrorsToRow(dish.local_id, e?.fieldErrors || {});
        if (e?.message) {
          setRowError(dish.local_id, "options", e.message);
        }
        throw e;
      }
    }
    for (const id of removedIds.value) {
      await dishApi.remove(id);
    }
    await flushPendingCleanup();
    removedIds.value = [];
    status.value = t("common.saved");
    toast.show(t("stepDishes.savedToast"), "success");
    emit("next");
  } catch (e) {
    status.value = t("common.saveFailed");
    globalError.value = e?.message || t("stepDishes.saveFailed");
    toast.show(globalError.value, "error");
  } finally {
    saving.value = false;
  }
};

onMounted(load);
</script>
