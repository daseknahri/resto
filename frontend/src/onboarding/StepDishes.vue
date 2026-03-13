<template>
  <div class="ui-panel space-y-4 p-5">
    <div class="ui-section-band rounded-[24px] p-4 sm:p-5">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t("stepDishes.title") }}</p>
          <h2 class="text-xl font-semibold text-white sm:text-2xl">{{ t("stepDishes.description") }}</h2>
        </div>
        <button v-if="sortedCategoryOptions.length" type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="openQuickDishModal">
          {{ t("stepDishes.addDishToCategory") }}
        </button>
      </div>
    </div>

    <div v-if="!sortedCategoryOptions.length" class="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 text-sm text-amber-100">
      {{ t("stepDishes.addCategoriesFirst") }}
    </div>

    <template v-else>
      <div class="ui-section-band space-y-3 rounded-[24px] p-4">
        <div class="flex flex-wrap items-center gap-2">
          <button
            v-for="category in sortedCategoryOptions"
            :key="category.id"
            type="button"
            class="ui-pill-nav text-xs"
            :class="String(category.id) === String(activeCategoryId) ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
            @click="setActiveCategory(category.id)"
          >
            {{ category.name }} ({{ dishCountForCategory(category.id) }})
          </button>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!hasPreviousCategory" @click="goToPreviousCategory">
            {{ t("stepDishes.previousCategory") }}
          </button>
          <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" :disabled="!hasNextCategory" @click="goToNextCategory">
            {{ t("stepDishes.nextCategory") }}
          </button>
          <span class="ui-data-strip">{{ activeCategoryRecord?.name }}</span>
          <span class="ui-data-strip">{{ activeCategoryDishes.length }} {{ t("common.dishes") }}</span>
        </div>
        <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
          <p class="text-xs text-slate-400">{{ t("stepDishes.translationsHint", { count: maxTranslationLocales }) }}</p>
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
        <div v-if="unassignedDishCount" class="rounded-2xl border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
          {{ t("stepDishes.unassignedWarning", { count: unassignedDishCount }) }}
        </div>
      </div>

      <div class="space-y-4">
        <div class="space-y-3">
          <template v-if="activeCategoryDishes.length">
            <div
              v-for="(dish, idx) in activeCategoryDishes"
              :key="dish.local_id"
              class="rounded-[26px] border border-slate-800 bg-slate-950/85 p-4 shadow-[0_18px_45px_rgba(2,8,23,0.22)] space-y-3"
            >
              <div class="flex flex-col gap-3 border-b border-slate-800/80 pb-3 sm:flex-row sm:items-start sm:justify-between">
                <div class="space-y-1">
                  <p class="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                    {{ t("stepDishes.dishCardLabel", { index: idx + 1 }) }}
                  </p>
                  <p class="text-sm text-slate-300">
                    {{ t("stepDishes.categoryPinned", { category: activeCategoryRecord?.name || t("stepDishes.selectCategory") }) }}
                  </p>
                </div>
                <button class="text-xs text-red-300" @click="removeDishByLocalId(dish.local_id)">
                  {{ t("stepDishes.removeDish") }}
                </button>
              </div>
  
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
                    <option v-for="cat in sortedCategoryOptions" :key="cat.id" :value="String(cat.id)">{{ cat.name }}</option>
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
            </div>
          </template>

          <div
            v-else
            class="rounded-[26px] border border-dashed border-slate-700 bg-slate-950/55 p-6 text-center"
          >
            <p class="text-sm font-semibold text-white">{{ t("stepDishes.emptyCategoryTitle", { category: activeCategoryRecord?.name || '' }) }}</p>
            <p class="mt-2 text-sm text-slate-400">{{ t("stepDishes.emptyCategoryText") }}</p>
            <button type="button" class="ui-btn-primary mt-4 px-4 py-2" @click="openQuickDishModal(activeCategoryId)">
              {{ t("stepDishes.addDishToCategory") }}
            </button>
          </div>
        </div>

      </div>
    </template>

    <Teleport to="body">
      <div
        v-if="quickDishModalOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
        @click.self="closeQuickDishModal"
      >
        <div class="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-950 p-4 shadow-2xl">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">{{ t("stepDishes.addDishToCategory") }}</h3>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeQuickDishModal">{{ t("common.close") }}</button>
          </div>
          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <select v-model="quickDish.category" class="ui-input">
              <option disabled value="">{{ t("stepDishes.selectCategory") }}</option>
              <option v-for="cat in sortedCategoryOptions" :key="cat.id" :value="String(cat.id)">{{ cat.name }}</option>
            </select>
            <input v-model="quickDish.name" class="ui-input" :placeholder="t('stepDishes.dishNamePlaceholder')" />
            <input v-model.number="quickDish.price" type="number" min="0" step="0.01" class="ui-input" :placeholder="t('stepDishes.pricePlaceholder')" />
            <input v-model="quickDish.image_url" class="ui-input" :placeholder="t('stepDishes.imageUrlPlaceholder')" />
            <textarea v-model="quickDish.description" rows="2" class="ui-textarea sm:col-span-2" :placeholder="t('stepDishes.descriptionPlaceholder')"></textarea>
          </div>
          <div class="mt-4 rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.variantsTitle") }}</p>
              <button
                type="button"
                class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-brand-secondary"
                @click="addQuickOption"
              >
                {{ t("stepDishes.addVariant") }}
              </button>
            </div>
            <p class="text-xs text-slate-500">{{ t("stepDishes.variantsHint") }}</p>

            <div v-if="quickDish.options.length" class="space-y-2">
              <div
                v-for="(option, idx) in quickDish.options"
                :key="option.local_id"
                class="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
              >
                <div class="grid gap-2 sm:grid-cols-[1fr,130px,130px,auto] sm:items-center">
                  <input
                    v-model="option.name"
                    class="ui-input"
                    :placeholder="t('stepDishes.variantNamePlaceholder')"
                  />
                  <input
                    v-model.number="option.price_delta"
                    type="number"
                    min="0"
                    step="0.01"
                    class="ui-input"
                    :placeholder="t('stepDishes.extraPricePlaceholder')"
                  />
                  <input
                    v-model.number="option.max_select"
                    type="number"
                    min="1"
                    step="1"
                    class="ui-input"
                    :placeholder="t('stepDishes.maxSelectPlaceholder')"
                  />
                  <button
                    type="button"
                    class="rounded-full border border-slate-700 px-3 py-2 text-xs text-red-200 hover:border-red-400/60"
                    @click="removeQuickOption(idx)"
                  >
                    {{ t("stepDishes.remove") }}
                  </button>
                </div>
                <label class="mt-2 inline-flex items-center gap-2 text-xs text-slate-300">
                  <input
                    v-model="option.is_required"
                    type="checkbox"
                    class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary"
                  />
                  {{ t("stepDishes.requiredBeforeAddToCart") }}
                </label>
              </div>
            </div>
            <p v-else class="text-xs text-slate-500">{{ t("stepDishes.noVariants") }}</p>
          </div>
          <div class="mt-4 flex justify-end gap-2">
            <button type="button" class="ui-btn-outline px-4 py-2 text-sm" @click="closeQuickDishModal">{{ t("common.close") }}</button>
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="quickAddDish">{{ t("stepDishes.addDishToCategory") }}</button>
          </div>
        </div>
      </div>
    </Teleport>

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
import { computed, reactive, ref, onMounted, watch } from "vue";
import { categoryApi, dishApi, dishOptionApi, uploadApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { LOCALE_OPTIONS, normalizeLocale } from "../i18n/config";
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
const activeCategoryId = ref("");
const quickDishModalOpen = ref(false);
const quickDish = reactive({
  category: "",
  name: "",
  description: "",
  price: 0,
  image_url: "",
  options: [],
});

const hasActiveUploads = computed(() => Object.values(uploadingRows).some(Boolean));
const maxTranslationLocales = computed(() =>
  Math.max(0, Number(tenant.entitlements?.max_languages || 1) - 1)
);
const defaultLocale = computed(() => normalizeLocale(tenant.resolvedMeta?.profile?.language || "en"));
const secondaryLocales = computed(() => LOCALE_OPTIONS.filter((option) => option.code !== defaultLocale.value));
const sortedCategoryOptions = computed(() =>
  [...categoryOptions.value].sort(
    (left, right) =>
      Number(left?.position ?? 0) - Number(right?.position ?? 0) ||
      String(left?.name || "").localeCompare(String(right?.name || ""))
  )
);
const activeCategoryRecord = computed(
  () => sortedCategoryOptions.value.find((category) => String(category.id) === String(activeCategoryId.value)) || null
);
const activeCategoryIndex = computed(() =>
  sortedCategoryOptions.value.findIndex((category) => String(category.id) === String(activeCategoryId.value))
);
const activeCategoryDishes = computed(() =>
  dishes.filter((dish) => String(dish.category || "") === String(activeCategoryId.value))
);
const hasPreviousCategory = computed(() => activeCategoryIndex.value > 0);
const hasNextCategory = computed(
  () => activeCategoryIndex.value >= 0 && activeCategoryIndex.value < sortedCategoryOptions.value.length - 1
);

const localeLabel = (code) => {
  const match = LOCALE_OPTIONS.find((option) => option.code === code);
  return match ? `${match.nativeLabel}` : String(code || "").toUpperCase();
};

const hasMeaningfulDishContent = (dish) =>
  Boolean(
    String(dish?.name || "").trim() ||
      String(dish?.description || "").trim() ||
      dish?.image_url ||
      Number(dish?.price || 0) > 0 ||
      (Array.isArray(dish?.options) && dish.options.length)
  );

const unassignedDishCount = computed(
  () => dishes.filter((dish) => !dish.category && hasMeaningfulDishContent(dish)).length
);

const dishCountForCategory = (categoryId) =>
  dishes.filter((dish) => String(dish.category || "") === String(categoryId)).length;

const syncActiveCategory = () => {
  if (!sortedCategoryOptions.value.length) {
    activeCategoryId.value = "";
    return;
  }
  const exists = sortedCategoryOptions.value.some(
    (category) => String(category.id) === String(activeCategoryId.value)
  );
  if (!exists) {
    activeCategoryId.value = String(sortedCategoryOptions.value[0].id);
  }
};

watch(sortedCategoryOptions, syncActiveCategory, { immediate: true });

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
  category: dish.category ? String(dish.category) : "",
  price: Number(dish.price || 0),
  currency: dish.currency || "USD",
  image_url: dish.image_url || "",
  description: dish.description || "",
  description_i18n: dish.description_i18n && typeof dish.description_i18n === "object" ? { ...dish.description_i18n } : {},
  position: dish.position ?? dishes.length,
  is_published: dish.is_published ?? true,
  options: Array.isArray(dish.options) ? dish.options.map((option) => normalizeOption(option)) : [],
});

const pickI18nMap = (input, allowedLocales = null) => {
  const out = {};
  if (!input || typeof input !== "object") return out;
  const allowed = Array.isArray(allowedLocales) ? new Set(allowedLocales.map((locale) => String(locale || "").trim().toLowerCase())) : null;
  Object.entries(input).forEach(([rawLocale, rawValue]) => {
    const locale = String(rawLocale || "").trim().toLowerCase();
    const value = String(rawValue || "").trim();
    if (!locale) return;
    if (allowed && !allowed.has(locale)) return;
    if (value) out[locale] = value;
  });
  return out;
};

const normalizeCurrency = (value) => {
  const cleaned = String(value || "USD").trim().toUpperCase();
  if (cleaned.length === 3 && /^[A-Z]{3}$/.test(cleaned)) return cleaned;
  return "USD";
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
  } catch {
    categoryOptions.value = [];
  }
  try {
    const data = await dishApi.list();
    const rows = data.length ? data.map(normalize) : [];
    dishes.splice(0, dishes.length, ...rows);
    hydrateTranslationLocalesFromRows(rows);
  } catch {
    status.value = t("common.loadFailed");
    dishes.splice(0, dishes.length);
    enforceTranslationLocaleSelection();
  }
  syncActiveCategory();
};

const setActiveCategory = (categoryId) => {
  activeCategoryId.value = String(categoryId || "");
};

const goToPreviousCategory = () => {
  if (!hasPreviousCategory.value) return;
  const previous = sortedCategoryOptions.value[activeCategoryIndex.value - 1];
  if (previous) setActiveCategory(previous.id);
};

const goToNextCategory = () => {
  if (!hasNextCategory.value) return;
  const next = sortedCategoryOptions.value[activeCategoryIndex.value + 1];
  if (next) setActiveCategory(next.id);
};

const resolveQuickDishCategory = (candidate = activeCategoryId.value) => {
  if (!sortedCategoryOptions.value.length) return "";
  const normalizedCandidate = String(candidate || "");
  if (
    normalizedCandidate &&
    sortedCategoryOptions.value.some((category) => String(category.id) === normalizedCandidate)
  ) {
    return normalizedCandidate;
  }
  const normalizedActive = String(activeCategoryId.value || "");
  if (
    normalizedActive &&
    sortedCategoryOptions.value.some((category) => String(category.id) === normalizedActive)
  ) {
    return normalizedActive;
  }
  return String(sortedCategoryOptions.value[0]?.id || "");
};

const resetQuickDish = (categoryId = activeCategoryId.value) => {
  quickDish.category = resolveQuickDishCategory(categoryId);
  quickDish.name = "";
  quickDish.description = "";
  quickDish.price = 0;
  quickDish.image_url = "";
  quickDish.options = [];
};

const openQuickDishModal = (categoryId = activeCategoryId.value) => {
  if (!sortedCategoryOptions.value.length) {
    toast.show(t("stepDishes.addCategoriesFirst"), "error");
    return;
  }
  resetQuickDish(categoryId);
  quickDishModalOpen.value = true;
};

const closeQuickDishModal = () => {
  quickDishModalOpen.value = false;
};

const addQuickOption = () => {
  quickDish.options.push(normalizeOption());
};

const removeQuickOption = (idx) => {
  quickDish.options.splice(idx, 1);
};

const quickAddDish = () => {
  const name = String(quickDish.name || "").trim();
  const category = resolveQuickDishCategory(quickDish.category);
  if (!category) {
    toast.show(t("stepDishes.selectCategoryError"), "error");
    return;
  }
  if (name.length < 2) {
    toast.show(t("stepDishes.nameMin"), "error");
    return;
  }
  dishes.push(
    normalize({
      category,
      name,
      description: String(quickDish.description || "").trim(),
      price: Number(quickDish.price) || 0,
      image_url: String(quickDish.image_url || "").trim(),
      position: dishes.length,
      options: (Array.isArray(quickDish.options) ? quickDish.options : [])
        .map((option) => normalizeOption(option))
        .filter(
          (option) =>
            String(option.name || "").trim() ||
            Number(option.price_delta || 0) !== 0 ||
            option.is_required === true ||
            Number(option.max_select || 1) !== 1
        ),
    })
  );
  setActiveCategory(category);
  closeQuickDishModal();
  toast.show(t("stepDishes.savedToast"), "success");
};

const remove = async (idx) => {
  const [dish] = dishes.splice(idx, 1);
  if (dish?.id) removedIds.value.push(dish.id);
  delete rowErrors[dish?.local_id];
  delete uploadingRows[dish?.local_id];
  delete uploadProgressRows[dish?.local_id];
  delete draggingRows[dish?.local_id];
  queueCleanup(dish?.image_url || "");
};

const removeDishByLocalId = async (localId) => {
  const index = dishes.findIndex((dish) => dish.local_id === localId);
  if (index >= 0) await remove(index);
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
    const allowedTranslationLocales = [...selectedTranslationLocales.value];
    for (const dish of validDishes) {
      try {
        const saved = await dishApi.upsert({
          ...dish,
          category: Number(dish.category) || dish.category,
          price: Number(dish.price) || 0,
          currency: normalizeCurrency(dish.currency),
          name_i18n: pickI18nMap(dish.name_i18n, allowedTranslationLocales),
          description_i18n: pickI18nMap(dish.description_i18n, allowedTranslationLocales),
        });
        dish.id = saved.id;
        dish.slug = saved.slug;
        const desiredOptions = Array.isArray(dish.options) ? dish.options : [];
        const savedOptions = await dishOptionApi.syncForDish(
          dish.id,
          desiredOptions.map((option) => ({
            ...option,
            name_i18n: pickI18nMap(option.name_i18n, allowedTranslationLocales),
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
