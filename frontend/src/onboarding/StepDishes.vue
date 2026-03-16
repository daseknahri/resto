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
        <div class="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center">
          <div class="space-y-1">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{{ t("stepDishes.selectCategory") }}</p>
            <select v-model="activeCategoryId" class="ui-input border-slate-700 bg-slate-950/70">
              <option v-for="category in sortedCategoryOptions" :key="category.id" :value="String(category.id)">
                {{ category.name }} ({{ dishCountForCategory(category.id) }})
              </option>
            </select>
          </div>
          <button type="button" class="ui-btn-outline px-3 py-2 text-xs" :disabled="!hasPreviousCategory" @click="goToPreviousCategory">
            {{ t("stepDishes.previousCategory") }}
          </button>
          <button type="button" class="ui-btn-outline px-3 py-2 text-xs" :disabled="!hasNextCategory" @click="goToNextCategory">
            {{ t("stepDishes.nextCategory") }}
          </button>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="ui-data-strip">{{ activeCategoryRecord?.name }}</span>
          <span class="ui-data-strip">{{ activeCategoryDishes.length }} {{ t("common.dishes") }}</span>
        </div>
        <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p class="text-xs text-slate-400">
            {{ t("stepDishes.translationsHint", { count: Math.max(0, availableContentLocales.length - 1) }) }}
          </p>
        </div>
        <div v-if="unassignedDishCount" class="rounded-2xl border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
          {{ t("stepDishes.unassignedWarning", { count: unassignedDishCount }) }}
        </div>
      </div>

      <div class="space-y-3">
        <template v-if="activeCategoryDishes.length">
          <article
            v-for="(dish, idx) in activeCategoryDishes"
            :key="dish.local_id"
            class="rounded-2xl border border-slate-800 bg-slate-950/75 p-4 shadow-[0_12px_28px_rgba(2,8,23,0.18)]"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1">
                <p class="text-[11px] uppercase tracking-[0.2em] text-slate-500">{{ t("stepDishes.dishCardLabel", { index: idx + 1 }) }}</p>
                <h3 class="mt-1 truncate text-base font-semibold text-white">{{ dish.name || t("stepDishes.dishNamePlaceholder") }}</h3>
                <p class="mt-1 line-clamp-2 text-sm text-slate-400">{{ dish.description || t("stepDishes.descriptionPlaceholder") }}</p>
                <div class="mt-2 flex flex-wrap gap-2">
                  <span class="ui-data-strip">{{ t("stepDishes.pricePlaceholder") }}: {{ Number(dish.price || 0).toFixed(2) }}</span>
                  <span class="ui-data-strip">{{ t("stepDishes.variantsTitle") }}: {{ Array.isArray(dish.options) ? dish.options.length : 0 }}</span>
                </div>
              </div>
              <img
                v-if="dish.image_url"
                :src="dish.image_url"
                alt=""
                class="h-14 w-14 rounded-xl border border-slate-700 object-cover"
              />
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button class="ui-btn-outline px-3 py-1.5 text-xs" type="button" @click="openDishEditor(dish.local_id)">
                Edit
              </button>
              <button class="rounded-full border border-red-400/25 px-3 py-1.5 text-xs text-red-200 hover:border-red-400/50" type="button" @click="removeDishByLocalId(dish.local_id)">
                {{ t("stepDishes.removeDish") }}
              </button>
            </div>
          </article>
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
    </template>

    <Teleport to="body">
      <div
        v-if="dishEditorModalOpen && editingDish"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        @click.self="closeDishEditor"
      >
        <div class="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 p-4 shadow-2xl sm:p-5 space-y-4">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-lg font-semibold text-white">{{ t("stepDishes.addDishToCategory") }}</h3>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeDishEditor">{{ t("common.close") }}</button>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-1">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-xs text-slate-400">{{ t("stepDishes.dishNamePlaceholder") }}</p>
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="locale in availableContentLocales"
                    :key="`dish-name-${locale.code}`"
                    type="button"
                    class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                    :class="dishFieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                    @click="dishFieldLocales.name = locale.code"
                  >
                    {{ locale.nativeLabel }}
                  </button>
                </div>
              </div>
              <input
                :value="localizedDishFieldValue(editingDish, 'name', dishFieldLocales.name)"
                class="ui-input"
                :class="rowError(editingDish, 'name') ? 'border-red-400' : 'border-slate-700'"
                :placeholder="t('stepDishes.dishNamePlaceholder')"
                @input="setLocalizedDishFieldValue(editingDish, 'name', dishFieldLocales.name, $event.target.value)"
              />
              <p v-if="rowError(editingDish, 'name')" class="text-xs text-red-300">{{ rowError(editingDish, "name") }}</p>
            </div>

            <div class="space-y-1">
              <select
                v-model="editingDish.category"
                class="ui-input"
                :class="rowError(editingDish, 'category') ? 'border-red-400' : 'border-slate-700'"
                @change="clearRowError(editingDish.local_id, 'category')"
              >
                <option disabled value="">{{ t("stepDishes.selectCategory") }}</option>
                <option v-for="cat in sortedCategoryOptions" :key="cat.id" :value="String(cat.id)">{{ cat.name }}</option>
              </select>
              <p v-if="rowError(editingDish, 'category')" class="text-xs text-red-300">{{ rowError(editingDish, "category") }}</p>
            </div>

            <div class="space-y-1">
              <input
                v-model.number="editingDish.price"
                type="number"
                min="0"
                step="0.01"
                class="ui-input"
                :class="rowError(editingDish, 'price') ? 'border-red-400' : 'border-slate-700'"
                :placeholder="t('stepDishes.pricePlaceholder')"
                @input="clearRowError(editingDish.local_id, 'price')"
              />
              <p v-if="rowError(editingDish, 'price')" class="text-xs text-red-300">{{ rowError(editingDish, "price") }}</p>
            </div>

            <div class="space-y-1">
              <div
                class="rounded-xl border border-dashed p-3 space-y-2 transition-colors"
                :class="draggingRows[editingDish.local_id] ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
                @dragenter="setDragState(editingDish.local_id, true)"
                @dragleave="setDragState(editingDish.local_id, false)"
                @dragover="preventDropDefaults"
                @drop="dropImage(editingDish, $event)"
              >
                <div class="flex flex-wrap items-center gap-3">
                  <label class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 cursor-pointer hover:border-brand-secondary">
                    {{ uploadingRows[editingDish.local_id] ? t("stepDishes.uploadingProgress", { progress: uploadProgressRows[editingDish.local_id] || 0 }) : t("stepDishes.uploadImage") }}
                    <input type="file" accept="image/*" class="hidden" :disabled="uploadingRows[editingDish.local_id]" @change="uploadImage(editingDish, $event)" />
                  </label>
                  <button
                    v-if="editingDish.image_url"
                    type="button"
                    class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-red-400 hover:text-red-300"
                    @click="clearImage(editingDish)"
                  >
                    {{ t("stepDishes.removeImage") }}
                  </button>
                  <img v-if="editingDish.image_url" :src="editingDish.image_url" alt="" class="h-10 w-10 rounded-lg object-cover border border-slate-700" />
                </div>
                <p class="text-xs text-slate-500">{{ t("stepDishes.dropImageHint") }}</p>
              </div>
              <p v-if="rowError(editingDish, 'image_url')" class="text-xs text-red-300">{{ rowError(editingDish, "image_url") }}</p>
              <p class="text-xs text-slate-500">{{ t("stepDishes.acceptedFormats") }}</p>
              <div v-if="uploadingRows[editingDish.local_id]" class="h-1.5 w-full rounded bg-slate-800 overflow-hidden">
                <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${uploadProgressRows[editingDish.local_id] || 0}%` }"></div>
              </div>
            </div>
          </div>

          <div class="space-y-1">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-xs text-slate-400">{{ t("stepDishes.descriptionPlaceholder") }}</p>
              <div class="flex flex-wrap gap-1">
                <button
                  v-for="locale in availableContentLocales"
                  :key="`dish-description-${locale.code}`"
                  type="button"
                  class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                  :class="dishFieldLocales.description === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                  @click="dishFieldLocales.description = locale.code"
                >
                  {{ locale.nativeLabel }}
                </button>
              </div>
            </div>
            <textarea
              :value="localizedDishFieldValue(editingDish, 'description', dishFieldLocales.description)"
              rows="2"
              class="ui-textarea"
              :class="rowError(editingDish, 'description') ? 'border-red-400' : 'border-slate-700'"
              :placeholder="t('stepDishes.descriptionPlaceholder')"
              @input="setLocalizedDishFieldValue(editingDish, 'description', dishFieldLocales.description, $event.target.value)"
            ></textarea>
          </div>
          <p v-if="rowError(editingDish, 'description')" class="text-xs text-red-300">{{ rowError(editingDish, "description") }}</p>

          <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.variantsTitle") }}</p>
              <button
                type="button"
                class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-brand-secondary"
                @click="addOption(editingDish)"
              >
                {{ t("stepDishes.addVariant") }}
              </button>
            </div>
            <p class="text-xs text-slate-500">{{ t("stepDishes.variantsHint") }}</p>

            <div v-if="editingDish.options?.length" class="space-y-2">
              <div
                v-for="(option, optIdx) in editingDish.options"
                :key="option.local_id"
                class="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
              >
                <div class="grid gap-2 sm:grid-cols-[1fr,130px,130px,auto] sm:items-center">
                  <div class="space-y-1">
                    <div class="flex flex-wrap items-center justify-between gap-2">
                      <p class="text-[11px] text-slate-400">{{ t("stepDishes.variantNamePlaceholder") }}</p>
                      <div class="flex flex-wrap gap-1">
                        <button
                          v-for="locale in availableContentLocales"
                          :key="`variant-name-${option.local_id}-${locale.code}`"
                          type="button"
                          class="rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors"
                          :class="dishFieldLocales.variantName === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                          @click="dishFieldLocales.variantName = locale.code"
                        >
                          {{ locale.nativeLabel }}
                        </button>
                      </div>
                    </div>
                    <input
                      :value="localizedVariantNameValue(option, dishFieldLocales.variantName)"
                      class="ui-input"
                      :class="rowError(editingDish, optionFieldKey(option, 'name')) ? 'border-red-400' : 'border-slate-700'"
                      :placeholder="t('stepDishes.variantNamePlaceholder')"
                      @input="setLocalizedVariantNameValue(editingDish, option, dishFieldLocales.variantName, $event.target.value)"
                    />
                  </div>
                  <input
                    v-model.number="option.price_delta"
                    type="number"
                    min="0"
                    step="0.01"
                    class="ui-input"
                    :class="rowError(editingDish, optionFieldKey(option, 'price_delta')) ? 'border-red-400' : 'border-slate-700'"
                    :placeholder="t('stepDishes.extraPricePlaceholder')"
                    @input="clearRowError(editingDish.local_id, optionFieldKey(option, 'price_delta'))"
                  />
                  <input
                    v-model.number="option.max_select"
                    type="number"
                    min="1"
                    step="1"
                    class="ui-input"
                    :class="rowError(editingDish, optionFieldKey(option, 'max_select')) ? 'border-red-400' : 'border-slate-700'"
                    :placeholder="t('stepDishes.maxSelectPlaceholder')"
                    @input="clearRowError(editingDish.local_id, optionFieldKey(option, 'max_select'))"
                  />
                  <button
                    type="button"
                    class="rounded-full border border-slate-700 px-3 py-2 text-xs text-red-200 hover:border-red-400/60"
                    @click="removeOption(editingDish, optIdx)"
                  >
                    {{ t("stepDishes.remove") }}
                  </button>
                </div>
                <label class="mt-2 inline-flex items-center gap-2 text-xs text-slate-300">
                  <input v-model="option.is_required" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
                  {{ t("stepDishes.requiredBeforeAddToCart") }}
                </label>
                <p v-if="rowError(editingDish, optionFieldKey(option, 'name'))" class="mt-1 text-xs text-red-300">{{ rowError(editingDish, optionFieldKey(option, "name")) }}</p>
                <p v-if="rowError(editingDish, optionFieldKey(option, 'price_delta'))" class="mt-1 text-xs text-red-300">{{ rowError(editingDish, optionFieldKey(option, "price_delta")) }}</p>
                <p v-if="rowError(editingDish, optionFieldKey(option, 'max_select'))" class="mt-1 text-xs text-red-300">{{ rowError(editingDish, optionFieldKey(option, "max_select")) }}</p>
              </div>
            </div>
            <p v-else class="text-xs text-slate-500">{{ t("stepDishes.noVariants") }}</p>
            <p v-if="rowError(editingDish, 'options')" class="text-xs text-red-300">{{ rowError(editingDish, "options") }}</p>
          </div>

          <p v-if="rowError(editingDish, 'slug')" class="text-xs text-red-300">{{ rowError(editingDish, "slug") }}</p>
          <p v-if="rowError(editingDish, 'non_field_errors')" class="text-xs text-red-300">{{ rowError(editingDish, "non_field_errors") }}</p>

          <div class="flex justify-end">
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="closeDishEditor">Done</button>
          </div>
        </div>
      </div>
    </Teleport>

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
            <div class="space-y-1">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-[11px] text-slate-400">{{ t("stepDishes.dishNamePlaceholder") }}</p>
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="locale in availableContentLocales"
                    :key="`quick-dish-name-${locale.code}`"
                    type="button"
                    class="rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors"
                    :class="quickDishFieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                    @click="quickDishFieldLocales.name = locale.code"
                  >
                    {{ locale.nativeLabel }}
                  </button>
                </div>
              </div>
              <input
                :value="localizedQuickDishFieldValue('name', quickDishFieldLocales.name)"
                class="ui-input"
                :placeholder="t('stepDishes.dishNamePlaceholder')"
                @input="setLocalizedQuickDishFieldValue('name', quickDishFieldLocales.name, $event.target.value)"
              />
            </div>
            <input v-model.number="quickDish.price" type="number" min="0" step="0.01" class="ui-input" :placeholder="t('stepDishes.pricePlaceholder')" />
            <div
              class="rounded-xl border border-dashed p-3 space-y-2 transition-colors"
              :class="draggingRows[quickDish.local_id] ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
              @dragenter="setDragState(quickDish.local_id, true)"
              @dragleave="setDragState(quickDish.local_id, false)"
              @dragover="preventDropDefaults"
              @drop="dropImage(quickDish, $event)"
            >
              <div class="flex flex-wrap items-center gap-3">
                <label class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 cursor-pointer hover:border-brand-secondary">
                  {{ uploadingRows[quickDish.local_id] ? t("stepDishes.uploadingProgress", { progress: uploadProgressRows[quickDish.local_id] || 0 }) : t("stepDishes.uploadImage") }}
                  <input type="file" accept="image/*" class="hidden" :disabled="uploadingRows[quickDish.local_id]" @change="uploadImage(quickDish, $event)" />
                </label>
                <button
                  v-if="quickDish.image_url"
                  type="button"
                  class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-slate-100 hover:border-red-400 hover:text-red-300"
                  @click="clearImage(quickDish)"
                >
                  {{ t("stepDishes.removeImage") }}
                </button>
                <img v-if="quickDish.image_url" :src="quickDish.image_url" alt="" class="h-10 w-10 rounded-lg object-cover border border-slate-700" />
              </div>
              <p class="text-xs text-slate-500">{{ t("stepDishes.dropImageHint") }}</p>
            </div>
            <div class="space-y-1 sm:col-span-2">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-[11px] text-slate-400">{{ t("stepDishes.descriptionPlaceholder") }}</p>
                <div class="flex flex-wrap gap-1">
                  <button
                    v-for="locale in availableContentLocales"
                    :key="`quick-dish-description-${locale.code}`"
                    type="button"
                    class="rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors"
                    :class="quickDishFieldLocales.description === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                    @click="quickDishFieldLocales.description = locale.code"
                  >
                    {{ locale.nativeLabel }}
                  </button>
                </div>
              </div>
              <textarea
                :value="localizedQuickDishFieldValue('description', quickDishFieldLocales.description)"
                rows="2"
                class="ui-textarea"
                :placeholder="t('stepDishes.descriptionPlaceholder')"
                @input="setLocalizedQuickDishFieldValue('description', quickDishFieldLocales.description, $event.target.value)"
              ></textarea>
            </div>
          </div>
          <p class="text-xs text-slate-500">{{ t("stepDishes.acceptedFormats") }}</p>
          <div v-if="uploadingRows[quickDish.local_id]" class="h-1.5 w-full rounded bg-slate-800 overflow-hidden">
            <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${uploadProgressRows[quickDish.local_id] || 0}%` }"></div>
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
                  <div class="space-y-1">
                    <div class="flex flex-wrap items-center justify-between gap-2">
                      <p class="text-[11px] text-slate-400">{{ t("stepDishes.variantNamePlaceholder") }}</p>
                      <div class="flex flex-wrap gap-1">
                        <button
                          v-for="locale in availableContentLocales"
                          :key="`quick-variant-name-${option.local_id}-${locale.code}`"
                          type="button"
                          class="rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors"
                          :class="quickDishFieldLocales.variantName === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                          @click="quickDishFieldLocales.variantName = locale.code"
                        >
                          {{ locale.nativeLabel }}
                        </button>
                      </div>
                    </div>
                    <input
                      :value="localizedQuickVariantNameValue(option, quickDishFieldLocales.variantName)"
                      class="ui-input"
                      :placeholder="t('stepDishes.variantNamePlaceholder')"
                      @input="setLocalizedQuickVariantNameValue(option, quickDishFieldLocales.variantName, $event.target.value)"
                    />
                  </div>
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
const activeCategoryId = ref("");
const dishEditorModalOpen = ref(false);
const dishEditorLocalId = ref("");
const dishFieldLocales = reactive({
  name: "en",
  description: "en",
  variantName: "en",
});
const quickDishModalOpen = ref(false);
const quickDish = reactive({
  local_id: "quick-dish",
  category: "",
  name: "",
  name_i18n: {},
  description: "",
  description_i18n: {},
  price: 0,
  image_url: "",
  options: [],
});
const quickDishFieldLocales = reactive({
  name: "en",
  description: "en",
  variantName: "en",
});
const editingDish = computed(
  () => dishes.find((dish) => String(dish.local_id) === String(dishEditorLocalId.value)) || null
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

const syncDishFieldLocales = () => {
  const allowed = new Set(availableContentLocales.value.map((locale) => locale.code));
  if (!allowed.has(dishFieldLocales.name)) dishFieldLocales.name = defaultLocale.value;
  if (!allowed.has(dishFieldLocales.description)) dishFieldLocales.description = defaultLocale.value;
  if (!allowed.has(dishFieldLocales.variantName)) dishFieldLocales.variantName = defaultLocale.value;
  if (!allowed.has(quickDishFieldLocales.name)) quickDishFieldLocales.name = defaultLocale.value;
  if (!allowed.has(quickDishFieldLocales.description)) quickDishFieldLocales.description = defaultLocale.value;
  if (!allowed.has(quickDishFieldLocales.variantName)) quickDishFieldLocales.variantName = defaultLocale.value;
};

watch([availableContentLocales, defaultLocale], syncDishFieldLocales, { immediate: true });

const localizedDishFieldValue = (dish, field, localeCode) => {
  if (!dish) return "";
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(dish[field] || "");
  const map = dish[`${field}_i18n`];
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};

const setLocalizedDishFieldValue = (dish, field, localeCode, value) => {
  if (!dish) return;
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    dish[field] = nextValue;
  } else {
    const mapField = `${field}_i18n`;
    if (!dish[mapField] || typeof dish[mapField] !== "object") dish[mapField] = {};
    if (nextValue.trim()) {
      dish[mapField][locale] = nextValue;
    } else {
      delete dish[mapField][locale];
    }
  }
  clearRowError(dish.local_id, field);
};

const localizedVariantNameValue = (option, localeCode) => {
  if (!option) return "";
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(option.name || "");
  const map = option.name_i18n;
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};

const setLocalizedVariantNameValue = (dish, option, localeCode, value) => {
  if (!dish || !option) return;
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    option.name = nextValue;
  } else {
    if (!option.name_i18n || typeof option.name_i18n !== "object") option.name_i18n = {};
    if (nextValue.trim()) {
      option.name_i18n[locale] = nextValue;
    } else {
      delete option.name_i18n[locale];
    }
  }
  clearRowError(dish.local_id, optionFieldKey(option, "name"));
};

const localizedQuickDishFieldValue = (field, localeCode) => {
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(quickDish[field] || "");
  const map = quickDish[`${field}_i18n`];
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};

const setLocalizedQuickDishFieldValue = (field, localeCode, value) => {
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    quickDish[field] = nextValue;
  } else {
    const mapField = `${field}_i18n`;
    if (!quickDish[mapField] || typeof quickDish[mapField] !== "object") quickDish[mapField] = {};
    if (nextValue.trim()) {
      quickDish[mapField][locale] = nextValue;
    } else {
      delete quickDish[mapField][locale];
    }
  }
};

const localizedQuickVariantNameValue = (option, localeCode) => {
  if (!option) return "";
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(option.name || "");
  const map = option.name_i18n;
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};

const setLocalizedQuickVariantNameValue = (option, localeCode, value) => {
  if (!option) return;
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    option.name = nextValue;
  } else {
    if (!option.name_i18n || typeof option.name_i18n !== "object") option.name_i18n = {};
    if (nextValue.trim()) {
      option.name_i18n[locale] = nextValue;
    } else {
      delete option.name_i18n[locale];
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
  } catch {
    status.value = t("common.loadFailed");
    dishes.splice(0, dishes.length);
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

const openDishEditor = (localId) => {
  dishEditorLocalId.value = String(localId || "");
  dishEditorModalOpen.value = true;
};

const closeDishEditor = () => {
  dishEditorModalOpen.value = false;
  dishEditorLocalId.value = "";
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
  quickDish.name_i18n = {};
  quickDish.description = "";
  quickDish.description_i18n = {};
  quickDish.price = 0;
  quickDish.image_url = "";
  quickDish.options = [];
  uploadingRows[quickDish.local_id] = false;
  uploadProgressRows[quickDish.local_id] = 0;
  draggingRows[quickDish.local_id] = false;
  quickDishFieldLocales.name = defaultLocale.value;
  quickDishFieldLocales.description = defaultLocale.value;
  quickDishFieldLocales.variantName = defaultLocale.value;
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
  if (quickDish.image_url && isManagedUpload(quickDish.image_url)) {
    cleanupManagedUpload(quickDish.image_url);
    quickDish.image_url = "";
  }
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
  const allowedTranslationLocales = availableContentLocales.value
    .map((locale) => locale.code)
    .filter((locale) => locale !== defaultLocale.value);
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
      name_i18n: pickI18nMap(quickDish.name_i18n, allowedTranslationLocales),
      description: String(quickDish.description || "").trim(),
      description_i18n: pickI18nMap(quickDish.description_i18n, allowedTranslationLocales),
      price: Number(quickDish.price) || 0,
      image_url: String(quickDish.image_url || "").trim(),
      position: dishes.length,
      options: (Array.isArray(quickDish.options) ? quickDish.options : [])
        .map((option) =>
          normalizeOption({
            ...option,
            name_i18n: pickI18nMap(option?.name_i18n, allowedTranslationLocales),
          })
        )
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
  if (String(dishEditorLocalId.value) === String(dish?.local_id || "")) {
    closeDishEditor();
  }
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
    const allowedTranslationLocales = availableContentLocales.value
      .map((locale) => locale.code)
      .filter((locale) => locale !== defaultLocale.value);
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
