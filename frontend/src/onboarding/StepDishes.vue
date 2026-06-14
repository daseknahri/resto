<template>
  <div class="ui-panel ui-reveal space-y-3 p-4">
    <div class="ui-section-band ui-reveal rounded-[24px] p-4 space-y-3">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="ui-kicker">{{ t("stepDishes.title") }}</p>
          <h2 class="text-xl font-semibold text-white sm:text-2xl">{{ t("common.dishes") }}</h2>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="ui-btn-outline px-4 py-2 text-sm" type="button" :disabled="saving || hasActiveUploads" @click="saveAndNext">
            {{ saving ? t("common.saving") : hasActiveUploads ? t("stepDishes.uploading") : t("common.save") }}
          </button>
          <button v-if="sortedCategoryOptions.length" type="button" class="ui-btn-outline gap-1.5 px-3 py-2 text-sm" @click="openBulkPriceModal">
            <AppIcon name="tag" class="h-3.5 w-3.5" aria-hidden="true" />
            {{ t("stepDishes.bulkPriceAdjust") }}
          </button>
          <button v-if="sortedCategoryOptions.length" type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="openQuickDishModal">
            {{ t("stepDishes.addDishToCategory") }}
          </button>
        </div>
      </div>
      <div class="ui-scroll-row">
        <span class="ui-data-strip">{{ activeCategoryDishesFiltered.length }} {{ t("common.dishes") }}</span>
        <span class="ui-data-strip">{{ sortedCategoryOptions.length }} {{ t("common.categories") }}</span>
        <span v-if="unassignedDishCount" class="ui-data-strip text-amber-200">{{ t("stepDishes.unassignedWarning", { count: unassignedDishCount }) }}</span>
      </div>
    </div>

    <div v-if="!sortedCategoryOptions.length" class="ui-empty-state flex items-start gap-3 p-5">
      <span class="relative z-10 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-amber-400/30 bg-amber-500/10 text-amber-300 shadow-lg shadow-black/20">
        <AppIcon name="info" class="h-5 w-5" aria-hidden="true" />
      </span>
      <p class="relative z-10 text-sm text-amber-100">{{ t("stepDishes.addCategoriesFirst") }}</p>
    </div>

    <template v-else>
      <div class="ui-section-band ui-reveal space-y-3 rounded-[24px] p-4" :style="{ '--ui-delay': '28ms' }">
        <div class="grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] lg:items-end">
          <div class="space-y-1">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">{{ t("stepDishes.selectCategory") }}</p>
            <select v-model="activeCategoryId" :aria-label="t('stepDishes.selectCategory')" class="ui-input border-slate-700 bg-slate-950/70">
              <option v-for="category in sortedCategoryOptions" :key="category.id" :value="String(category.id)">
                {{ categoryLabel(category) }} ({{ dishCountForCategory(category.id) }})
              </option>
            </select>
          </div>
          <label class="text-sm text-slate-300">
            <span class="sr-only">{{ t("common.search") }}</span>
            <input v-model.trim="dishSearch" type="search" class="ui-input border-slate-700 bg-slate-950/70" enterkeyhint="search" :placeholder="t('common.search')" />
          </label>
          <button type="button" class="ui-btn-outline px-3 py-2 text-xs" :disabled="!hasPreviousCategory" @click="goToPreviousCategory">
            {{ t("stepDishes.previousCategory") }}
          </button>
          <button type="button" class="ui-btn-outline px-3 py-2 text-xs" :disabled="!hasNextCategory" @click="goToNextCategory">
            {{ t("stepDishes.nextCategory") }}
          </button>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="ui-data-strip">{{ activeCategoryRecord?.name }}</span>
          <span class="ui-data-strip">{{ activeCategoryDishesFiltered.length }} {{ t("common.dishes") }}</span>
          <button type="button" class="ui-btn-outline ui-press px-3 py-1 text-xs" @click="publishAllInCategory">
            {{ t("stepDishes.bulkPublish") }}
          </button>
          <button type="button" class="ui-btn-outline ui-press px-3 py-1 text-xs" @click="unpublishAllInCategory">
            {{ t("stepDishes.bulkUnpublish") }}
          </button>
        </div>
      </div>

      <div class="space-y-1.5 ui-reveal" :style="{ '--ui-delay': '56ms' }">
        <ul v-if="activeCategoryDishesFiltered.length" class="space-y-1.5">
          <li
            v-for="(dish, index) in activeCategoryDishesFiltered"
            :key="dish.local_id"
            class="ui-surface-lift ui-reveal group flex items-center gap-2.5 rounded-xl border border-slate-800 bg-slate-950/70 p-2 transition hover:border-slate-700 sm:gap-3 sm:p-2.5"
            :class="dish.is_published ? '' : 'opacity-70'"
            :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms`, 'content-visibility': 'auto', 'contain-intrinsic-size': 'auto 68px' }"
          >
            <!-- Reorder: stacked chevrons -->
            <div class="flex shrink-0 flex-col">
              <button
                class="ui-press ui-touch-target flex items-center justify-center rounded text-slate-500 transition hover:text-white disabled:opacity-20"
                type="button" :disabled="!canMoveDishUp(dish.local_id)" :aria-label="t('common.moveUp')"
                @click="moveDish(dish.local_id, -1)"
              >
                <AppIcon name="chevronUp" class="h-4 w-4" />
              </button>
              <button
                class="ui-press ui-touch-target flex items-center justify-center rounded text-slate-500 transition hover:text-white disabled:opacity-20"
                type="button" :disabled="!canMoveDishDown(dish.local_id)" :aria-label="t('common.moveDown')"
                @click="moveDish(dish.local_id, 1)"
              >
                <AppIcon name="chevronDown" class="h-4 w-4" />
              </button>
            </div>

            <!-- Thumbnail (placeholder when no image) -->
            <img
              v-if="dish.image_url"
              :src="dish.image_url" alt="" loading="lazy" decoding="async"
              class="h-11 w-11 shrink-0 rounded-lg border border-slate-700 object-cover"
              @error="$event.target.style.display='none'"
            />
            <div v-else class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-slate-800 bg-slate-900/80 text-slate-600">
              <AppIcon name="cart" class="h-4 w-4" />
            </div>

            <!-- Name + meta — the whole block opens the editor -->
            <button type="button" class="min-w-0 flex-1 text-start" :aria-label="`${t('common.edit')} ${dish.name || t('stepDishes.dishNamePlaceholder')}`" @click="openDishEditor(dish.local_id)">
              <div class="flex items-center gap-1.5">
                <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="dish.is_published ? 'bg-emerald-400' : 'bg-slate-600'" />
                <h3 class="truncate text-sm font-semibold text-white">{{ dish.name || t("stepDishes.dishNamePlaceholder") }}</h3>
              </div>
              <div class="mt-0.5 flex items-center gap-1.5 truncate text-xs text-slate-500">
                <span class="font-semibold tabular-nums text-slate-300">{{ Number(dish.price || 0).toFixed(2) }}</span>
                <span v-if="Array.isArray(dish.options) && dish.options.length">· {{ dish.options.length }} {{ t("stepDishes.variantsTitle") }}</span>
                <span v-if="dish.option_groups?.length" class="text-sky-300">· {{ dish.option_groups.length }} {{ t("stepDishes.optionGroupsTitle") }}</span>
                <span v-if="dish.combo_components?.length" class="rounded-full border border-violet-500/40 bg-violet-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-violet-300">{{ t("combos.badge") }}</span>
                <span v-if="dish.attributes?.brand || dish.attributes?.unit" class="text-[11px] text-slate-500">· {{ [dish.attributes?.brand, dish.attributes?.unit].filter(Boolean).join(" · ") }}</span>
              </div>
            </button>

            <!-- Inline actions: publish switch · edit · delete -->
            <div class="flex shrink-0 items-center gap-1.5">
              <label
                class="inline-flex cursor-pointer items-center"
                :title="dish.is_published ? t('stepPublish.published') : t('stepPublish.draft')"
              >
                <input
                  v-model="dish.is_published"
                  type="checkbox"
                  class="peer sr-only"
                  role="switch"
                  :aria-checked="dish.is_published ? 'true' : 'false'"
                  :aria-label="dish.is_published ? t('stepPublish.published') : t('stepPublish.draft')"
                />
                <span class="relative h-5 w-9 rounded-full bg-slate-700 transition after:absolute after:start-0.5 after:top-0.5 after:h-4 after:w-4 after:rounded-full after:bg-white after:transition peer-checked:bg-emerald-500/80 peer-checked:after:translate-x-4" />
              </label>
              <button
                class="ui-press ui-touch-target flex items-center justify-center rounded-lg border border-slate-700 text-slate-300 transition hover:border-slate-500 hover:text-white"
                type="button" :aria-label="t('common.edit')" @click="openDishEditor(dish.local_id)"
              >
                <AppIcon name="pencil" class="h-3.5 w-3.5" />
              </button>
              <button
                class="ui-press ui-touch-target flex items-center justify-center rounded-lg border border-slate-700 text-slate-400 transition hover:border-slate-500 hover:text-white"
                type="button" :aria-label="t('stepDishes.cloneDish')" :title="t('stepDishes.cloneDish')" @click="cloneDish(dish.local_id)"
              >
                <AppIcon name="copy" class="h-3.5 w-3.5" />
              </button>
              <button
                class="ui-press ui-touch-target flex items-center justify-center rounded-lg border border-red-400/25 text-red-300 transition hover:border-red-400/50 hover:text-red-200"
                type="button" :aria-label="t('stepDishes.removeDish')" @click="removeDishByLocalId(dish.local_id)"
              >
                <AppIcon name="trash" class="h-3.5 w-3.5" />
              </button>
            </div>
          </li>
        </ul>

        <div
          v-else
          class="ui-empty-state flex flex-col items-start gap-4 p-5 text-start sm:flex-row sm:items-center sm:justify-between"
        >
          <div class="relative z-10 flex items-start gap-3">
            <span class="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-slate-700/70 bg-slate-900/75 text-[var(--color-secondary)] shadow-lg shadow-black/25">
              <AppIcon :name="dishSearch ? 'search' : 'filter'" class="h-5 w-5" aria-hidden="true" />
            </span>
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("stepDishes.title") }}</p>
              <h3 class="text-base font-semibold text-white">{{ dishSearch ? `${t("common.search")} — 0` : t("stepDishes.emptyCategoryTitle", { category: activeCategoryRecord?.name || '' }) }}</h3>
              <p v-if="!dishSearch" class="max-w-xl text-sm text-slate-400">{{ t("stepDishes.emptyCategoryText") }}</p>
            </div>
          </div>
          <button v-if="!dishSearch" type="button" class="ui-btn-primary relative z-10 px-4 py-2 text-sm" @click="openQuickDishModal(activeCategoryId)">
            {{ t("stepDishes.addDishToCategory") }}
          </button>
        </div>
      </div>
    </template>

    <Teleport to="body">
      <div
        v-if="dishEditorModalOpen && editingDish"
        class="fixed inset-0 z-[2100] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        @click.self="closeDishEditor"
      >
        <div ref="dishEditorDialogRef" role="dialog" aria-modal="true" aria-labelledby="step-dishes-editor-dialog-title" tabindex="-1" class="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4 sm:px-5">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("common.dishes") }}</p>
              <h3 id="step-dishes-editor-dialog-title" class="text-lg font-semibold text-white">{{ t("stepDishes.editDish") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeDishEditor">{{ t("common.close") }}</button>
          </div>

          <div class="space-y-4 px-4 pt-4 pb-5 sm:px-5 sm:pt-5">
            <div class="ui-scroll-row">
              <span class="ui-data-strip">{{ activeCategoryRecord?.name || t("stepDishes.selectCategory") }}</span>
              <span class="ui-data-strip">{{ t("stepDishes.pricePlaceholder") }}: {{ Number(editingDish.price || 0).toFixed(2) }}</span>
              <span class="ui-data-strip">{{ t("stepDishes.variantsTitle") }}: {{ Array.isArray(editingDish.options) ? editingDish.options.length : 0 }}</span>
            </div>

            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4">
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="space-y-1">
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <p class="text-xs text-slate-400">{{ t("stepDishes.dishNamePlaceholder") }}</p>
                    <div class="flex flex-wrap gap-1">
                      <button
                        v-for="locale in availableContentLocales"
                        :key="`dish-name-${locale.code}`"
                        type="button"
                        :aria-pressed="dishFieldLocales.name === locale.code"
                        class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                        :class="dishFieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                        @click="dishFieldLocales.name = locale.code"
                      >
                        {{ locale.nativeLabel }}
                      </button>
                      <button
                        v-if="dishFieldLocales.name !== defaultLocale && localizedDishFieldValue(editingDish, 'name', defaultLocale)"
                        type="button"
                        class="rounded-full border border-sky-700/60 px-2.5 py-1 text-[11px] font-semibold text-sky-300 transition-colors hover:border-sky-500 hover:text-sky-200 disabled:opacity-50"
                        :disabled="dishTranslating[`${editingDish.local_id}_name`]"
                        @click="runDishTranslate(editingDish, 'name', dishFieldLocales.name)"
                      >
                        {{ dishTranslating[`${editingDish.local_id}_name`] ? t("common.translating") : t("common.translate") }}
                      </button>
                    </div>
                  </div>
                  <input
                    type="text"
                    :value="localizedDishFieldValue(editingDish, 'name', dishFieldLocales.name)"
                    class="ui-input"
                    :class="rowError(editingDish, 'name') ? 'border-red-400' : 'border-slate-700'"
                    :placeholder="t('stepDishes.dishNamePlaceholder')"
                    :aria-label="t('stepDishes.dishNamePlaceholder')"
                    :aria-invalid="rowError(editingDish, 'name') ? 'true' : undefined"
                    :aria-describedby="`step-dishes-name-error-${editingDish.local_id}`"
                    @input="setLocalizedDishFieldValue(editingDish, 'name', dishFieldLocales.name, $event.target.value)"
                  />
                  <p v-if="rowError(editingDish, 'name')" :id="`step-dishes-name-error-${editingDish.local_id}`" class="text-xs text-red-300" role="alert">{{ rowError(editingDish, "name") }}</p>
                </div>

                <div class="space-y-1">
                  <p class="text-[11px] text-slate-400">{{ t("stepDishes.selectCategory") }}</p>
                  <select
                    v-model="editingDish.category"
                    :aria-label="t('stepDishes.selectCategory')"
                    class="ui-input"
                    :class="rowError(editingDish, 'category') ? 'border-red-400' : 'border-slate-700'"
                    :aria-invalid="rowError(editingDish, 'category') ? 'true' : undefined"
                    :aria-describedby="`step-dishes-category-error-${editingDish.local_id}`"
                    @change="clearRowError(editingDish.local_id, 'category')"
                  >
                    <option disabled value="">{{ t("stepDishes.selectCategory") }}</option>
                    <option v-for="cat in sortedCategoryOptions" :key="cat.id" :value="String(cat.id)">{{ categoryLabel(cat) }}</option>
                  </select>
                  <p v-if="rowError(editingDish, 'category')" :id="`step-dishes-category-error-${editingDish.local_id}`" class="text-xs text-red-300" role="alert">{{ rowError(editingDish, "category") }}</p>
                </div>

                <div class="space-y-1">
                  <p class="text-[11px] text-slate-400">{{ t("stepDishes.pricePlaceholder") }}</p>
                  <input
                    v-model.number="editingDish.price"
                    type="number"
                    min="0"
                    step="0.01"
                    class="ui-input"
                    :class="rowError(editingDish, 'price') ? 'border-red-400' : 'border-slate-700'"
                    :placeholder="t('stepDishes.pricePlaceholder')"
                    :aria-label="t('stepDishes.pricePlaceholder')"
                    :aria-invalid="rowError(editingDish, 'price') ? 'true' : undefined"
                    :aria-describedby="`step-dishes-price-error-${editingDish.local_id}`"
                    @input="clearRowError(editingDish.local_id, 'price')"
                  />
                  <p v-if="rowError(editingDish, 'price')" :id="`step-dishes-price-error-${editingDish.local_id}`" class="text-xs text-red-300" role="alert">{{ rowError(editingDish, "price") }}</p>
                </div>

                <div class="space-y-1">
                  <p class="text-[11px] text-slate-400">{{ t("stepDishes.dishSlug") }}</p>
                  <input
                    v-model.trim="editingDish.slug"
                    type="text"
                    class="ui-input border-slate-700 font-mono text-sm"
                    :placeholder="t('stepDishes.dishSlug')"
                    :aria-label="t('stepDishes.dishSlug')"
                    :aria-invalid="rowError(editingDish, 'slug') ? 'true' : undefined"
                    :aria-describedby="`step-dishes-slug-error-${editingDish.local_id}`"
                    @input="clearRowError(editingDish.local_id, 'slug')"
                  />
                  <p v-if="rowError(editingDish, 'slug')" :id="`step-dishes-slug-error-${editingDish.local_id}`" class="text-xs text-red-300" role="alert">{{ rowError(editingDish, "slug") }}</p>
                </div>

                <!-- Stock qty — null = unlimited; positive integer = tracked inventory -->
                <div class="space-y-1">
                  <p class="text-[11px] text-slate-400">{{ t("stepDishes.stockQtyLabel") }}</p>
                  <input
                    :value="editingDish.stock_qty ?? ''"
                    type="number"
                    min="0"
                    step="1"
                    class="ui-input border-slate-700"
                    :aria-label="t('stepDishes.stockQtyLabel')"
                    :placeholder="t('stepDishes.stockQtyPlaceholder')"
                    @change="editingDish.stock_qty = $event.target.value === '' ? null : Math.max(0, parseInt($event.target.value, 10) || 0)"
                  />
                  <p class="text-[10px] text-slate-600">{{ t("stepDishes.stockQtyHint") }}</p>
                </div>

                <div
                  class="rounded-xl border border-dashed p-3 transition-colors"
                  :class="draggingRows[editingDish.local_id] ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
                  @dragenter="setDragState(editingDish.local_id, true)"
                  @dragleave="setDragState(editingDish.local_id, false)"
                  @dragover="preventDropDefaults"
                  @drop="dropImage(editingDish, $event)">
                  <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-3">
                      <img v-if="editingDish.image_url" :src="editingDish.image_url" alt="" loading="lazy" decoding="async" class="h-12 w-12 rounded-xl border border-slate-700 object-cover" @error="$event.target.style.display='none'" />
                      <div class="min-w-0">
                        <p class="text-xs font-medium text-slate-100">{{ t("stepDishes.uploadImage") }}</p>
                        <p class="text-xs text-slate-500">{{ t("stepDishes.acceptedFormats") }}</p>
                      </div>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
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
                    </div>
                  </div>
                  <p class="mt-3 text-xs text-slate-500">{{ t("stepDishes.dropImageHint") }}</p>
                  <div v-if="uploadingRows[editingDish.local_id]" class="mt-3 h-1.5 w-full rounded bg-slate-800 overflow-hidden">
                    <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${uploadProgressRows[editingDish.local_id] || 0}%` }"></div>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4 space-y-3">
              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepDishes.descriptionPlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`dish-description-${locale.code}`"
                      type="button"
                      :aria-pressed="dishFieldLocales.description === locale.code"
                      class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      :class="dishFieldLocales.description === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                      @click="dishFieldLocales.description = locale.code"
                    >
                      {{ locale.nativeLabel }}
                    </button>
                    <button
                      v-if="dishFieldLocales.description !== defaultLocale && localizedDishFieldValue(editingDish, 'description', defaultLocale)"
                      type="button"
                      class="rounded-full border border-sky-700/60 px-2.5 py-1 text-[11px] font-semibold text-sky-300 transition-colors hover:border-sky-500 hover:text-sky-200 disabled:opacity-50"
                      :disabled="dishTranslating[`${editingDish.local_id}_description`]"
                      @click="runDishTranslate(editingDish, 'description', dishFieldLocales.description)"
                    >
                      {{ dishTranslating[`${editingDish.local_id}_description`] ? t("common.translating") : t("common.translate") }}
                    </button>
                  </div>
                </div>
                <textarea
                  :value="localizedDishFieldValue(editingDish, 'description', dishFieldLocales.description)"
                  rows="3"
                  class="ui-textarea"
                  :class="rowError(editingDish, 'description') ? 'border-red-400' : 'border-slate-700'"
                  :aria-label="t('common.description')"
                  :aria-invalid="rowError(editingDish, 'description') ? 'true' : undefined"
                  :aria-describedby="`step-dishes-description-error-${editingDish.local_id}`"
                  :placeholder="t('stepDishes.descriptionPlaceholder')"
                  @input="setLocalizedDishFieldValue(editingDish, 'description', dishFieldLocales.description, $event.target.value)"
                ></textarea>
              </div>
              <p v-if="rowError(editingDish, 'description')" :id="`step-dishes-description-error-${editingDish.local_id}`" class="text-xs text-red-300" role="alert">{{ rowError(editingDish, "description") }}</p>

              <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
                <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.tagsTitle") }}</p>
                <div class="flex flex-wrap gap-2">
                  <label
                    v-for="tag in DISH_TAGS"
                    :key="tag"
                    class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors select-none"
                    :class="editingDish.tags?.includes(tag) ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-300 hover:border-slate-600'"
                  >
                    <input type="checkbox" class="sr-only" :checked="editingDish.tags?.includes(tag)" @change="toggleTag(editingDish, tag, $event.target.checked)" />
                    {{ t(`stepDishes.tag_${tag}`) }}
                  </label>
                </div>
              </div>

              <!-- Allergen declarations -->
              <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
                <div class="flex items-center justify-between gap-2">
                  <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.allergensTitle") }}</p>
                  <p class="text-[10px] text-slate-500">{{ t("stepDishes.allergensHint") }}</p>
                </div>
                <div class="flex flex-wrap gap-2">
                  <label
                    v-for="allergen in ALLERGENS"
                    :key="allergen"
                    class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors select-none"
                    :class="editingDish.allergens?.includes(allergen) ? 'border-amber-400/70 bg-amber-400/10 text-amber-300' : 'border-slate-700 text-slate-300 hover:border-amber-400/40'"
                  >
                    <input type="checkbox" class="sr-only" :checked="editingDish.allergens?.includes(allergen)" @change="toggleAllergen(editingDish, allergen, $event.target.checked)" />
                    {{ t(`stepDishes.allergen_${allergen}`) }}
                  </label>
                </div>
              </div>

              <!-- Product details (retail only) -->
              <div v-if="isShop" class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
                <div>
                  <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.productDetails") }}</p>
                  <p class="text-xs text-slate-500">{{ t("stepDishes.productDetailsHint") }}</p>
                </div>
                <div class="grid gap-2 sm:grid-cols-2">
                  <div class="space-y-1">
                    <p class="text-[11px] text-slate-400">{{ t("stepDishes.attrSku") }}</p>
                    <input
                      v-model.trim="editingDish.attributes.sku"
                      type="text"
                      class="ui-input border-slate-700"
                      :aria-label="t('stepDishes.attrSku')"
                      :placeholder="t('stepDishes.attrSku')"
                    />
                  </div>
                  <div class="space-y-1">
                    <p class="text-[11px] text-slate-400">{{ t("stepDishes.attrBarcode") }}</p>
                    <input
                      v-model.trim="editingDish.attributes.barcode"
                      type="text"
                      class="ui-input border-slate-700"
                      :aria-label="t('stepDishes.attrBarcode')"
                      :placeholder="t('stepDishes.attrBarcode')"
                    />
                  </div>
                  <div class="space-y-1">
                    <p class="text-[11px] text-slate-400">{{ t("stepDishes.attrBrand") }}</p>
                    <input
                      v-model.trim="editingDish.attributes.brand"
                      type="text"
                      class="ui-input border-slate-700"
                      :aria-label="t('stepDishes.attrBrand')"
                      :placeholder="t('stepDishes.attrBrand')"
                    />
                  </div>
                  <div class="space-y-1">
                    <p class="text-[11px] text-slate-400">{{ t("stepDishes.attrUnit") }}</p>
                    <input
                      v-model.trim="editingDish.attributes.unit"
                      type="text"
                      class="ui-input border-slate-700"
                      :aria-label="t('stepDishes.attrUnit')"
                      :placeholder="t('stepDishes.attrUnitPlaceholder')"
                    />
                  </div>
                </div>
              </div>

              <!-- Availability schedule -->
              <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-3">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.availabilityTitle") }}</p>
                    <p class="text-xs text-slate-500">{{ t("stepDishes.availabilityHint") }}</p>
                  </div>
                  <label class="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-300 select-none">
                    <input
                      type="checkbox"
                      :checked="!!editingDish.availability_schedule"
                      class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary"
                      @change="toggleDishAvailabilitySchedule(editingDish, $event.target.checked)"
                    />
                    {{ t("stepDishes.availabilityRestrict") }}
                  </label>
                </div>

                <div v-if="editingDish.availability_schedule" class="space-y-3">
                  <div class="space-y-1.5">
                    <p class="text-xs text-slate-400">{{ t("stepDishes.availabilityDays") }}</p>
                    <div class="flex flex-wrap gap-2">
                      <label
                        v-for="day in WEEKDAYS"
                        :key="day.key"
                        class="inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors select-none"
                        :class="(editingDish.availability_schedule.days || []).includes(day.key)
                          ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary'
                          : 'border-slate-700 text-slate-300 hover:border-slate-600'"
                      >
                        <input
                          type="checkbox"
                          class="sr-only"
                          :checked="(editingDish.availability_schedule.days || []).includes(day.key)"
                          @change="toggleAvailabilityDay(editingDish, day.key, $event.target.checked)"
                        />
                        {{ t(`stepDishes.weekday_${day.key}`) }}
                      </label>
                    </div>
                    <p class="text-[10px] text-slate-600">{{ t("stepDishes.availabilityDaysHint") }}</p>
                  </div>

                  <div class="flex flex-wrap items-end gap-4">
                    <div class="space-y-1">
                      <p class="text-xs text-slate-400">{{ t("stepDishes.availabilityFrom") }}</p>
                      <input
                        v-model="editingDish.availability_schedule.time_start"
                        type="time"
                        class="ui-input w-32 border-slate-700"
                        :aria-label="t('stepDishes.availabilityFrom')"
                      />
                    </div>
                    <div class="space-y-1">
                      <p class="text-xs text-slate-400">{{ t("stepDishes.availabilityTo") }}</p>
                      <input
                        v-model="editingDish.availability_schedule.time_end"
                        type="time"
                        class="ui-input w-32 border-slate-700"
                        :aria-label="t('stepDishes.availabilityTo')"
                      />
                    </div>
                    <p class="pb-1 text-[10px] text-slate-600">{{ t("stepDishes.availabilityTimeHint") }}</p>
                  </div>
                </div>
              </div>

              <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.variantsTitle") }}</p>
              <button
                type="button"
                class="ui-btn-outline ui-press px-3 py-1.5 text-xs"
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
                          :aria-pressed="dishFieldLocales.variantName === locale.code"
                          class="rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors"
                          :class="dishFieldLocales.variantName === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                          @click="dishFieldLocales.variantName = locale.code"
                        >
                          {{ locale.nativeLabel }}
                        </button>
                      </div>
                    </div>
                    <input
                      type="text"
                      :value="localizedVariantNameValue(option, dishFieldLocales.variantName)"
                      class="ui-input"
                      :class="rowError(editingDish, optionFieldKey(option, 'name')) ? 'border-red-400' : 'border-slate-700'"
                      :placeholder="t('stepDishes.variantNamePlaceholder')"
                      :aria-label="t('stepDishes.variantNamePlaceholder')"
                      :aria-invalid="rowError(editingDish, optionFieldKey(option, 'name')) ? 'true' : undefined"
                      :aria-describedby="`step-dishes-opt-name-error-${option.local_id}`"
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
                    :aria-label="t('stepDishes.extraPricePlaceholder')"
                    :aria-invalid="rowError(editingDish, optionFieldKey(option, 'price_delta')) ? 'true' : undefined"
                    :aria-describedby="`step-dishes-opt-price-error-${option.local_id}`"
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
                    :aria-label="t('stepDishes.maxSelectPlaceholder')"
                    :aria-invalid="rowError(editingDish, optionFieldKey(option, 'max_select')) ? 'true' : undefined"
                    :aria-describedby="`step-dishes-opt-maxselect-error-${option.local_id}`"
                    @input="clearRowError(editingDish.local_id, optionFieldKey(option, 'max_select'))"
                  />
                  <button
                    type="button"
                    class="rounded-full border border-slate-700 px-3 py-2 text-xs text-red-200 hover:border-red-400/60"
                    :aria-label="`${t('stepDishes.remove')} ${localizedVariantNameValue(option, dishFieldLocales.variantName) || t('stepDishes.variantNamePlaceholder')}`"
                    @click="removeOption(editingDish, optIdx)"
                  >
                    {{ t("stepDishes.remove") }}
                  </button>
                </div>
                <div class="mt-2 flex flex-wrap items-center gap-3">
                  <label class="inline-flex items-center gap-2 text-xs text-slate-300">
                    <input v-model="option.is_required" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
                    {{ t("stepDishes.requiredBeforeAddToCart") }}
                  </label>
                  <div class="ms-auto flex items-center gap-1">
                    <button type="button" class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:border-slate-500 disabled:opacity-30" :disabled="!canMoveOptionUp(editingDish, optIdx)" :aria-label="t('common.moveUp')" @click="moveOption(editingDish, optIdx, -1)">↑</button>
                    <button type="button" class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:border-slate-500 disabled:opacity-30" :disabled="!canMoveOptionDown(editingDish, optIdx)" :aria-label="t('common.moveDown')" @click="moveOption(editingDish, optIdx, 1)">↓</button>
                  </div>
                </div>
                <p v-if="rowError(editingDish, optionFieldKey(option, 'name'))" :id="`step-dishes-opt-name-error-${option.local_id}`" class="mt-1 text-xs text-red-300" role="alert">{{ rowError(editingDish, optionFieldKey(option, "name")) }}</p>
                <p v-if="rowError(editingDish, optionFieldKey(option, 'price_delta'))" :id="`step-dishes-opt-price-error-${option.local_id}`" class="mt-1 text-xs text-red-300" role="alert">{{ rowError(editingDish, optionFieldKey(option, "price_delta")) }}</p>
                <p v-if="rowError(editingDish, optionFieldKey(option, 'max_select'))" :id="`step-dishes-opt-maxselect-error-${option.local_id}`" class="mt-1 text-xs text-red-300" role="alert">{{ rowError(editingDish, optionFieldKey(option, "max_select")) }}</p>
              </div>
            </div>
            <p v-else class="text-xs text-slate-500">{{ t("stepDishes.noVariants") }}</p>
            <p v-if="rowError(editingDish, 'options')" :id="`step-dishes-options-error-${editingDish.local_id}`" class="text-xs text-red-300" role="alert">{{ rowError(editingDish, "options") }}</p>
              </div>

              <div class="rounded-xl border border-sky-900/40 bg-sky-950/20 p-3 space-y-3">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.optionGroupsTitle") }}</p>
                    <p class="text-xs text-slate-500">{{ t("stepDishes.optionGroupsHint") }}</p>
                  </div>
                  <button
                    type="button"
                    class="ui-btn-outline ui-press px-3 py-1.5 text-xs"
                    @click="addGroup(editingDish)"
                  >
                    {{ t("stepDishes.addGroup") }}
                  </button>
                </div>

                <div v-if="editingDish.option_groups?.length" class="space-y-3">
                  <div
                    v-for="(group, groupIdx) in editingDish.option_groups"
                    :key="group.local_id"
                    class="rounded-lg border border-slate-700/60 bg-slate-900/60 p-3 space-y-2"
                  >
                    <div class="space-y-2">
                      <div class="space-y-1">
                        <div class="flex flex-wrap items-center justify-between gap-2">
                          <p class="text-[11px] text-slate-400">{{ t("stepDishes.groupNamePlaceholder") }}</p>
                          <div class="flex flex-wrap gap-1">
                            <button
                              v-for="locale in availableContentLocales"
                              :key="`group-name-${group.local_id}-${locale.code}`"
                              type="button"
                              :aria-pressed="dishFieldLocales.groupName === locale.code"
                              class="rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors"
                              :class="dishFieldLocales.groupName === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                              @click="dishFieldLocales.groupName = locale.code"
                            >
                              {{ locale.nativeLabel }}
                            </button>
                          </div>
                        </div>
                        <input
                          type="text"
                          :value="localizedGroupNameValue(group, dishFieldLocales.groupName)"
                          class="ui-input w-full"
                          :aria-label="t('stepDishes.groupNamePlaceholder')"
                          :placeholder="t('stepDishes.groupNamePlaceholder')"
                          @input="setLocalizedGroupNameValue(group, dishFieldLocales.groupName, $event.target.value)"
                        />
                      </div>
                      <div class="flex flex-wrap items-center gap-2">
                        <label class="inline-flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                          <input
                            type="checkbox"
                            :checked="group.min_select > 0"
                            class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary"
                            @change="group.min_select = $event.target.checked ? 1 : 0"
                          />
                          {{ t("stepDishes.groupRequired") }}
                        </label>
                        <div class="flex items-center gap-1.5">
                          <p class="text-[11px] text-slate-400">{{ t("stepDishes.groupMaxSelect") }}</p>
                          <input
                            v-model.number="group.max_select"
                            type="number"
                            min="1"
                            class="ui-input w-16 border-slate-700 text-xs"
                            :aria-label="t('stepDishes.groupMaxSelect')"
                          />
                        </div>
                        <div class="ms-auto flex items-center gap-1">
                          <button type="button" class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:border-slate-500 disabled:opacity-30" :disabled="!canMoveGroupUp(editingDish, groupIdx)" :aria-label="t('common.moveUp')" @click="moveGroup(editingDish, groupIdx, -1)">↑</button>
                          <button type="button" class="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:border-slate-500 disabled:opacity-30" :disabled="!canMoveGroupDown(editingDish, groupIdx)" :aria-label="t('common.moveDown')" @click="moveGroup(editingDish, groupIdx, 1)">↓</button>
                        </div>
                        <button
                          type="button"
                          class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-red-200 hover:border-red-400/60 shrink-0"
                          :aria-label="`${t('stepDishes.remove')} ${localizedGroupNameValue(group, dishFieldLocales.groupName) || t('stepDishes.groupNamePlaceholder')}`"
                          @click="removeGroup(editingDish, groupIdx)"
                        >
                          {{ t("stepDishes.remove") }}
                        </button>
                      </div>
                    </div>

                    <div v-if="group.options?.length" class="space-y-2 pl-1">
                      <div
                        v-for="(opt, optIdx) in group.options"
                        :key="opt.local_id"
                        class="space-y-1"
                      >
                        <div class="flex flex-wrap items-center justify-between gap-1">
                          <p class="text-[11px] text-slate-400">{{ t("stepDishes.variantNamePlaceholder") }}</p>
                          <div class="flex flex-wrap gap-1">
                            <button
                              v-for="locale in availableContentLocales"
                              :key="`group-opt-name-${opt.local_id}-${locale.code}`"
                              type="button"
                              :aria-pressed="dishFieldLocales.groupOptionName === locale.code"
                              class="rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors"
                              :class="dishFieldLocales.groupOptionName === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                              @click="dishFieldLocales.groupOptionName = locale.code"
                            >
                              {{ locale.nativeLabel }}
                            </button>
                          </div>
                        </div>
                        <div class="flex items-center gap-2">
                          <input
                            type="text"
                            :value="localizedGroupOptionNameValue(opt, dishFieldLocales.groupOptionName)"
                            class="ui-input flex-1 min-w-0"
                            :aria-label="t('stepDishes.variantNamePlaceholder')"
                            :placeholder="t('stepDishes.variantNamePlaceholder')"
                            @input="setLocalizedGroupOptionNameValue(opt, dishFieldLocales.groupOptionName, $event.target.value)"
                          />
                          <input
                            v-model.number="opt.price_delta"
                            type="number"
                            min="0"
                            step="0.01"
                            class="ui-input w-24 shrink-0"
                            :aria-label="t('stepDishes.extraPricePlaceholder')"
                            :placeholder="t('stepDishes.extraPricePlaceholder')"
                          />
                          <button type="button" class="rounded border border-slate-700 px-1.5 py-1 text-xs text-slate-400 hover:border-slate-500 disabled:opacity-30 shrink-0" :disabled="!canMoveGroupOptionUp(group, optIdx)" :aria-label="t('common.moveUp')" @click="moveGroupOption(group, optIdx, -1)">↑</button>
                          <button type="button" class="rounded border border-slate-700 px-1.5 py-1 text-xs text-slate-400 hover:border-slate-500 disabled:opacity-30 shrink-0" :disabled="!canMoveGroupOptionDown(group, optIdx)" :aria-label="t('common.moveDown')" @click="moveGroupOption(group, optIdx, 1)">↓</button>
                          <button
                            type="button"
                            class="rounded-full border border-slate-700 px-2.5 py-1.5 text-xs text-red-200 hover:border-red-400/60 shrink-0"
                            :aria-label="`${t('stepDishes.remove')} ${localizedGroupOptionNameValue(opt, dishFieldLocales.groupOptionName) || t('stepDishes.variantNamePlaceholder')}`"
                            @click="removeGroupOption(group, optIdx)"
                          >
                            {{ t("stepDishes.remove") }}
                          </button>
                        </div>
                      </div>
                    </div>

                    <button
                      type="button"
                      class="rounded-full border border-slate-700/60 px-3 py-1 text-xs text-slate-400 hover:text-slate-200 hover:border-slate-600"
                      @click="addGroupOption(group)"
                    >
                      {{ t("stepDishes.addGroupOption") }}
                    </button>
                  </div>
                </div>
                <p v-else class="text-xs text-slate-500">{{ t("stepDishes.noGroups") }}</p>
              </div>

              <!-- Combo builder -->
              <div class="rounded-xl border border-violet-900/40 bg-violet-950/15 p-3 space-y-3">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p class="text-sm font-semibold text-slate-100">{{ t("combos.builderToggle") }}</p>
                    <p class="text-xs text-slate-500">{{ t("combos.builderHint") }}</p>
                  </div>
                  <label class="inline-flex cursor-pointer items-center gap-2 text-xs text-slate-300 select-none">
                    <input
                      type="checkbox"
                      :checked="editingDish.combo_components?.length > 0"
                      class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-violet-500"
                      @change="toggleComboMode(editingDish, $event.target.checked)"
                    />
                    {{ t("combos.badge") }}
                  </label>
                </div>

                <template v-if="editingDish.combo_components?.length > 0">
                  <!-- Savings hint -->
                  <p v-if="comboSavings(editingDish) > 0" class="text-xs font-semibold text-emerald-400">
                    {{ t("combos.savings", { amount: Number(comboSavings(editingDish)).toFixed(2) }) }}
                  </p>

                  <!-- Component rows -->
                  <ul class="space-y-2">
                    <li
                      v-for="(comp, compIdx) in editingDish.combo_components"
                      :key="compIdx"
                      class="flex items-center gap-2 rounded-lg border border-slate-700/60 bg-slate-900/60 px-3 py-2 text-sm"
                    >
                      <span class="min-w-0 flex-1 text-slate-200">{{ comp.name || comp.component_id }}</span>
                      <div class="flex shrink-0 items-center gap-1">
                        <span class="text-[11px] text-slate-400">{{ t("combos.componentQty") }}</span>
                        <input
                          :value="comp.qty"
                          type="number"
                          min="1"
                          max="9"
                          step="1"
                          class="ui-input w-14 border-slate-700 text-xs"
                          :aria-label="t('combos.componentQty')"
                          @change="comp.qty = Math.min(9, Math.max(1, parseInt($event.target.value, 10) || 1))"
                        />
                      </div>
                      <button
                        type="button"
                        class="shrink-0 rounded-full border border-slate-700 px-2.5 py-1 text-xs text-red-300 hover:border-red-400/50"
                        :aria-label="t('combos.removeComponent')"
                        @click="removeComboComponent(editingDish, compIdx)"
                      >
                        {{ t("combos.removeComponent") }}
                      </button>
                    </li>
                  </ul>

                  <!-- Add component picker -->
                  <div v-if="editingDish.combo_components.length < 8" class="flex flex-wrap items-center gap-2">
                    <select
                      v-model="comboPicker[editingDish.local_id]"
                      class="ui-input flex-1 border-slate-700 text-sm"
                      :aria-label="t('combos.addComponent')"
                    >
                      <option value="">{{ t("combos.addComponent") }}</option>
                      <option
                        v-for="d in availableComboComponents(editingDish)"
                        :key="d.id"
                        :value="String(d.id)"
                      >{{ d.name }}</option>
                    </select>
                    <button
                      type="button"
                      class="ui-btn-outline px-3 py-2 text-xs"
                      @click="addComboComponent(editingDish)"
                    >{{ t("combos.addComponent") }}</button>
                  </div>
                  <p v-else class="text-[11px] text-slate-500">{{ t("combos.maxComponents") }}</p>
                </template>
              </div>

              <p v-if="rowError(editingDish, 'image_url')" :id="`step-dishes-image-error-${editingDish.local_id}`" class="text-xs text-red-300" role="alert">{{ rowError(editingDish, "image_url") }}</p>
              <p v-if="rowError(editingDish, 'non_field_errors')" class="text-xs text-red-300" role="alert">{{ rowError(editingDish, "non_field_errors") }}</p>
            </div>
          </div>

          <div class="sticky bottom-0 z-10 flex justify-end gap-2 border-t border-slate-800 bg-slate-950/95 px-4 py-4 sm:px-5">
            <button type="button" class="ui-btn-outline px-4 py-2 text-sm" @click="closeDishEditor">{{ t("common.close") }}</button>
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" :disabled="savingDishNow" @click="saveDishNow">
              {{ savingDishNow ? t("common.saving") : t("common.save") }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="quickDishModalOpen"
        class="fixed inset-0 z-[2100] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
        @click.self="closeQuickDishModal"
      >
        <div ref="quickDishDialogRef" role="dialog" aria-modal="true" aria-labelledby="step-dishes-quick-dialog-title" tabindex="-1" class="w-full max-w-3xl rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("common.dishes") }}</p>
              <h3 id="step-dishes-quick-dialog-title" class="text-lg font-semibold text-white">{{ t("stepDishes.addDishToCategory") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeQuickDishModal">{{ t("common.close") }}</button>
          </div>

          <div class="space-y-4 p-4">
            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4">
              <div class="grid gap-3 sm:grid-cols-2">
                <div class="space-y-1">
                  <select
                    v-model="quickDish.category"
                    :aria-label="t('stepDishes.selectCategory')"
                    class="ui-input"
                    :class="quickDishErrors.category ? 'border-red-400' : ''"
                    :aria-invalid="quickDishErrors.category ? 'true' : undefined"
                    aria-describedby="step-dishes-quick-category-error"
                    @change="quickDishErrors.category = ''"
                  >
                    <option disabled value="">{{ t("stepDishes.selectCategory") }}</option>
                    <option v-for="cat in sortedCategoryOptions" :key="cat.id" :value="String(cat.id)">{{ categoryLabel(cat) }}</option>
                  </select>
                  <p v-if="quickDishErrors.category" id="step-dishes-quick-category-error" class="text-xs text-red-300">{{ quickDishErrors.category }}</p>
                </div>
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
                      <button
                        v-if="quickDishFieldLocales.name !== defaultLocale && localizedQuickDishFieldValue('name', defaultLocale)"
                        type="button"
                        class="rounded-full border border-sky-700/60 px-2 py-0.5 text-[10px] font-semibold text-sky-300 transition-colors hover:border-sky-500 hover:text-sky-200 disabled:opacity-50"
                        :disabled="dishTranslating['quick_name']"
                        @click="runQuickDishTranslate('name', quickDishFieldLocales.name)"
                      >
                        {{ dishTranslating["quick_name"] ? t("common.translating") : t("common.translate") }}
                      </button>
                    </div>
                  </div>
                  <input
                    ref="quickDishNameInputRef"
                    type="text"
                    :value="localizedQuickDishFieldValue('name', quickDishFieldLocales.name)"
                    class="ui-input"
                    :class="quickDishErrors.name ? 'border-red-400' : ''"
                    :placeholder="t('stepDishes.dishNamePlaceholder')"
                    :aria-label="t('stepDishes.dishNamePlaceholder')"
                    :aria-invalid="quickDishErrors.name ? 'true' : undefined"
                    aria-describedby="step-dishes-quick-name-error"
                    @input="setLocalizedQuickDishFieldValue('name', quickDishFieldLocales.name, $event.target.value); quickDishErrors.name = ''"
                  />
                  <p v-if="quickDishErrors.name" id="step-dishes-quick-name-error" class="text-xs text-red-300 mt-1">{{ quickDishErrors.name }}</p>
                </div>
                <input v-model.number="quickDish.price" type="number" min="0" step="0.01" class="ui-input" :aria-label="t('stepDishes.pricePlaceholder')" :placeholder="t('stepDishes.pricePlaceholder')" />
                <div
                  class="rounded-xl border border-dashed p-3 transition-colors"
                  :class="draggingRows[quickDish.local_id] ? 'border-brand-secondary bg-brand-secondary/10' : 'border-slate-700 bg-slate-900/40'"
                  @dragenter="setDragState(quickDish.local_id, true)"
                  @dragleave="setDragState(quickDish.local_id, false)"
                  @dragover="preventDropDefaults"
                  @drop="dropImage(quickDish, $event)"
                >
                  <div class="flex flex-wrap items-center justify-between gap-3">
                    <div class="flex min-w-0 items-center gap-3">
                      <img v-if="quickDish.image_url" :src="quickDish.image_url" alt="" loading="lazy" decoding="async" class="h-12 w-12 rounded-xl border border-slate-700 object-cover" @error="$event.target.style.display='none'" />
                      <div class="min-w-0">
                        <p class="text-xs font-medium text-slate-100">{{ t("stepDishes.uploadImage") }}</p>
                        <p class="text-xs text-slate-500">{{ t("stepDishes.acceptedFormats") }}</p>
                      </div>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
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
                    </div>
                  </div>
                  <p class="mt-3 text-xs text-slate-500">{{ t("stepDishes.dropImageHint") }}</p>
                  <div v-if="uploadingRows[quickDish.local_id]" class="mt-3 h-1.5 w-full rounded bg-slate-800 overflow-hidden">
                    <div class="h-full bg-emerald-400 transition-all duration-150" :style="{ width: `${uploadProgressRows[quickDish.local_id] || 0}%` }"></div>
                  </div>
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
                      <button
                        v-if="quickDishFieldLocales.description !== defaultLocale && localizedQuickDishFieldValue('description', defaultLocale)"
                        type="button"
                        class="rounded-full border border-sky-700/60 px-2 py-0.5 text-[10px] font-semibold text-sky-300 transition-colors hover:border-sky-500 hover:text-sky-200 disabled:opacity-50"
                        :disabled="dishTranslating['quick_description']"
                        @click="runQuickDishTranslate('description', quickDishFieldLocales.description)"
                      >
                        {{ dishTranslating["quick_description"] ? t("common.translating") : t("common.translate") }}
                      </button>
                    </div>
                  </div>
                  <textarea
                    :value="localizedQuickDishFieldValue('description', quickDishFieldLocales.description)"
                    rows="3"
                    class="ui-textarea"
                    :aria-label="t('common.description')"
                    :placeholder="t('stepDishes.descriptionPlaceholder')"
                    @input="setLocalizedQuickDishFieldValue('description', quickDishFieldLocales.description, $event.target.value)"
                  ></textarea>
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4">
              <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 space-y-2">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.variantsTitle") }}</p>
                  <button
                    type="button"
                    class="ui-btn-outline ui-press px-3 py-1.5 text-xs"
                    @click="addQuickOption"
                  >
                    {{ t("stepDishes.addVariant") }}
                  </button>
                </div>

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
                              :aria-pressed="quickDishFieldLocales.variantName === locale.code"
                              class="rounded-full border px-2 py-0.5 text-[10px] font-semibold transition-colors"
                              :class="quickDishFieldLocales.variantName === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                              @click="quickDishFieldLocales.variantName = locale.code"
                            >
                              {{ locale.nativeLabel }}
                            </button>
                          </div>
                        </div>
                        <input
                          type="text"
                          :value="localizedQuickVariantNameValue(option, quickDishFieldLocales.variantName)"
                          class="ui-input"
                          :aria-label="t('stepDishes.variantNamePlaceholder')"
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
                        :aria-label="t('stepDishes.extraPricePlaceholder')"
                        :placeholder="t('stepDishes.extraPricePlaceholder')"
                      />
                      <input
                        v-model.number="option.max_select"
                        type="number"
                        min="1"
                        step="1"
                        class="ui-input"
                        :aria-label="t('stepDishes.maxSelectPlaceholder')"
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

              <div class="rounded-xl border border-sky-900/40 bg-sky-950/20 p-3 space-y-2">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-sm font-semibold text-slate-100">{{ t("stepDishes.optionGroupsTitle") }}</p>
                  <button type="button" class="ui-btn-outline ui-press px-3 py-1.5 text-xs" @click="addQuickGroup">
                    {{ t("stepDishes.addGroup") }}
                  </button>
                </div>
                <div v-if="quickDish.option_groups.length" class="space-y-3">
                  <div v-for="(group, groupIdx) in quickDish.option_groups" :key="group.local_id" class="rounded-lg border border-slate-700/60 bg-slate-900/60 p-3 space-y-2">
                    <div class="flex flex-wrap items-center gap-2">
                      <input v-model="group.name" type="text" class="ui-input flex-1 min-w-0" :aria-label="t('stepDishes.groupNamePlaceholder')" :placeholder="t('stepDishes.groupNamePlaceholder')" />
                      <label class="inline-flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer shrink-0">
                        <input type="checkbox" :checked="group.min_select > 0" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" @change="group.min_select = $event.target.checked ? 1 : 0" />
                        {{ t("stepDishes.groupRequired") }}
                      </label>
                      <button type="button" class="rounded-full border border-slate-700 px-3 py-1.5 text-xs text-red-200 hover:border-red-400/60 shrink-0" @click="removeQuickGroup(groupIdx)">
                        {{ t("stepDishes.remove") }}
                      </button>
                    </div>
                    <div v-if="group.options?.length" class="space-y-1.5 pl-1">
                      <div v-for="(opt, optIdx) in group.options" :key="opt.local_id" class="flex items-center gap-2">
                        <input v-model="opt.name" type="text" class="ui-input flex-1 min-w-0" :aria-label="t('stepDishes.variantNamePlaceholder')" :placeholder="t('stepDishes.variantNamePlaceholder')" />
                        <input v-model.number="opt.price_delta" type="number" min="0" step="0.01" class="ui-input w-24 shrink-0" :aria-label="t('stepDishes.extraPricePlaceholder')" :placeholder="t('stepDishes.extraPricePlaceholder')" />
                        <button type="button" class="rounded-full border border-slate-700 px-2.5 py-1.5 text-xs text-red-200 hover:border-red-400/60 shrink-0" @click="removeQuickGroupOption(group, optIdx)">
                          {{ t("stepDishes.remove") }}
                        </button>
                      </div>
                    </div>
                    <button type="button" class="rounded-full border border-slate-700/60 px-3 py-1 text-xs text-slate-400 hover:text-slate-200 hover:border-slate-600" @click="addQuickGroupOption(group)">
                      {{ t("stepDishes.addGroupOption") }}
                    </button>
                  </div>
                </div>
                <p v-else class="text-xs text-slate-500">{{ t("stepDishes.noGroups") }}</p>
              </div>
            </div>
          </div>

          <div class="sticky bottom-0 z-10 flex justify-end gap-2 border-t border-slate-800 bg-slate-950/95 px-4 py-4">
            <button type="button" class="ui-btn-outline px-4 py-2 text-sm" @click="closeQuickDishModal">{{ t("common.close") }}</button>
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="quickAddDish">{{ t("stepDishes.addDishToCategory") }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Bulk price adjustment modal ────────────────────────────────────── -->
    <Teleport to="body">
      <div
        v-if="bulkPriceModalOpen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        :aria-label="t('stepDishes.bulkPriceTitle')"
        @click.self="closeBulkPriceModal"
      >
        <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" aria-hidden="true" />
        <div
          ref="bulkPriceDialogRef"
          class="relative z-10 w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl"
        >
          <!-- Header -->
          <div class="flex items-center justify-between border-b border-slate-800 px-5 py-4">
            <div>
              <h2 class="text-base font-semibold text-white">{{ t("stepDishes.bulkPriceTitle") }}</h2>
              <p class="mt-0.5 text-xs text-slate-400">{{ t("stepDishes.bulkPriceSubtitle") }}</p>
            </div>
            <button type="button" class="ui-icon-btn" :aria-label="t('common.close')" @click="closeBulkPriceModal">
              <AppIcon name="x" class="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          <!-- Body -->
          <div class="space-y-4 px-5 py-4">
            <!-- Action type -->
            <div>
              <label class="ui-label mb-1.5 block">{{ t("stepDishes.bulkPriceActionLabel") }}</label>
              <div class="grid grid-cols-2 gap-2">
                <button
                  v-for="opt in [
                    { value: 'increase_percent', label: t('stepDishes.bulkPriceIncreasePercent') },
                    { value: 'decrease_percent', label: t('stepDishes.bulkPriceDecreasePercent') },
                    { value: 'increase_flat',    label: t('stepDishes.bulkPriceIncreaseFlat') },
                    { value: 'decrease_flat',    label: t('stepDishes.bulkPriceDecreaseFlat') },
                  ]"
                  :key="opt.value"
                  type="button"
                  class="rounded-xl border px-3 py-2 text-sm transition"
                  :class="bulkPriceAction === opt.value
                    ? 'border-violet-500 bg-violet-500/15 text-violet-300'
                    : 'border-slate-700 bg-slate-800/60 text-slate-300 hover:border-slate-500'"
                  @click="bulkPriceAction = opt.value; bulkPricePreview = []"
                >{{ opt.label }}</button>
              </div>
            </div>

            <!-- Value + Scope row -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="ui-label mb-1.5 block">{{ t("stepDishes.bulkPriceValue") }}</label>
                <input
                  v-model="bulkPriceValue"
                  type="number"
                  min="0.01"
                  :max="isPercentAction ? 100 : undefined"
                  step="0.01"
                  class="ui-input w-full"
                  :placeholder="isPercentAction ? t('stepDishes.bulkPriceValueHintPercent') : t('stepDishes.bulkPriceValueHintFlat')"
                  @input="bulkPricePreview = []"
                />
              </div>
              <div>
                <label class="ui-label mb-1.5 block">{{ t("stepDishes.bulkPriceScopeLabel") }}</label>
                <select v-model="bulkPriceCategoryId" class="ui-select w-full" @change="bulkPricePreview = []">
                  <option value="">{{ t("stepDishes.bulkPriceScopeAll") }}</option>
                  <option v-for="cat in sortedCategoryOptions" :key="cat.id" :value="String(cat.id)">
                    {{ categoryLabel(cat) }}
                  </option>
                </select>
              </div>
            </div>

            <!-- Rounding -->
            <div>
              <label class="ui-label mb-1.5 block">{{ t("stepDishes.bulkPriceRoundLabel") }}</label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="opt in [
                    { value: 0,   label: t('stepDishes.bulkPriceRoundNone') },
                    { value: 50,  label: t('stepDishes.bulkPriceRound50') },
                    { value: 100, label: t('stepDishes.bulkPriceRound100') },
                    { value: 500, label: t('stepDishes.bulkPriceRound500') },
                  ]"
                  :key="opt.value"
                  type="button"
                  class="rounded-lg border px-3 py-1.5 text-xs transition"
                  :class="bulkPriceRoundTo === opt.value
                    ? 'border-violet-500 bg-violet-500/15 text-violet-300'
                    : 'border-slate-700 bg-slate-800/60 text-slate-300 hover:border-slate-500'"
                  @click="bulkPriceRoundTo = opt.value; bulkPricePreview = []"
                >{{ opt.label }}</button>
              </div>
            </div>

            <!-- Error -->
            <p v-if="bulkPriceError" class="text-sm text-red-400">{{ bulkPriceError }}</p>

            <!-- Preview table -->
            <div v-if="bulkPricePreview.length" class="max-h-48 overflow-y-auto rounded-xl border border-slate-700 bg-slate-800/50">
              <table class="w-full text-sm">
                <thead class="sticky top-0 bg-slate-900/90">
                  <tr class="text-left text-xs text-slate-400">
                    <th class="px-3 py-2">{{ t("stepDishes.bulkPriceColItem") }}</th>
                    <th class="px-3 py-2 text-right">{{ t("stepDishes.bulkPriceColBefore") }}</th>
                    <th class="px-3 py-2 text-right">{{ t("stepDishes.bulkPriceColAfter") }}</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-700/50">
                  <tr v-for="item in bulkPricePreview" :key="item.id" class="text-slate-300">
                    <td class="max-w-[180px] truncate px-3 py-2">{{ item.name }}</td>
                    <td class="px-3 py-2 text-right tabular-nums text-slate-400">{{ item.old_price }}</td>
                    <td class="px-3 py-2 text-right tabular-nums font-medium text-emerald-400">{{ item.new_price }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-else-if="!bulkPriceLoading" class="text-sm text-slate-500">
              {{ t("stepDishes.bulkPricePreviewEmpty") }}
            </p>
            <div v-if="bulkPriceLoading" class="flex items-center justify-center py-4">
              <span class="h-5 w-5 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
            </div>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between border-t border-slate-800 px-5 py-4">
            <button type="button" class="ui-btn-outline px-4 py-2 text-sm" @click="closeBulkPriceModal">
              {{ t("common.cancel") }}
            </button>
            <div class="flex gap-2">
              <button
                type="button"
                class="ui-btn-outline px-4 py-2 text-sm"
                :disabled="bulkPriceLoading"
                @click="previewBulkPrice"
              >
                {{ bulkPriceLoading ? "…" : t("stepDishes.bulkPricePreviewBtn") }}
              </button>
              <button
                v-if="bulkPricePreview.length"
                type="button"
                class="ui-btn-primary px-4 py-2 text-sm"
                :disabled="bulkPriceApplying"
                @click="applyBulkPrice"
              >
                {{ bulkPriceApplying
                    ? t("stepDishes.bulkPriceApplying")
                    : t("stepDishes.bulkPriceApplyBtn", { count: bulkPricePreview.length }) }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <div v-if="globalError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <svg aria-hidden="true" viewBox="0 0 20 20" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
      <p class="flex-1 text-sm text-red-300">{{ globalError }}</p>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <button type="button" class="ui-btn-primary px-4 py-2" :disabled="saving || hasActiveUploads" @click="saveAndNext">
        {{ saving ? t("common.saving") : hasActiveUploads ? t("stepDishes.uploading") : props.standalone ? t("common.save") : t("common.saveAndNext") }}
      </button>
      <button v-if="!props.standalone" type="button" class="ui-btn-outline px-4 py-2" @click="$emit('back')">{{ t("common.previous") }}</button>
      <p class="text-sm text-slate-400">{{ status }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { categoryApi, dishApi, dishOptionApi, optionGroupApi, uploadApi } from "../lib/onboardingApi";
import api from "../lib/api";
import { useI18n } from "../composables/useI18n";
import { useFocusTrap } from "../composables/useFocusTrap";
import { useTranslate } from "../composables/useTranslate";
import { useVocabulary } from "../composables/useVocabulary";
import { LOCALE_OPTIONS, normalizeLocale } from "../i18n/config";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";
import { useConfirmModal } from "../composables/useConfirmModal";

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
const dishSearch = ref("");
const toast = useToastStore();
const { confirm } = useConfirmModal();
const tenant = useTenantStore();
const { isShop } = useVocabulary();
const { t } = useI18n();
const { translating: dishTranslating, translateError: dishTranslateError, translateField } = useTranslate();
const emit = defineEmits(["next", "back"]);
const DISH_TAGS = ["vegan", "vegetarian", "spicy", "gluten_free", "dairy_free", "nuts", "halal", "kosher"];
const ALLERGENS = [
  "gluten", "crustaceans", "eggs", "fish", "peanuts", "soy",
  "milk", "tree_nuts", "celery", "mustard", "sesame",
  "sulphites", "lupin", "molluscs",
];
import { useRoute } from "vue-router";
const props = defineProps({
  standalone: {
    type: Boolean,
    default: false,
  },
});
const route = useRoute();
const activeCategoryId = ref("");
const dishEditorModalOpen = ref(false);
const dishEditorDialogRef = ref(null);
const dishEditorLocalId = ref("");
const dishFieldLocales = reactive({
  name: "en",
  description: "en",
  variantName: "en",
  groupName: "en",
  groupOptionName: "en",
});
const quickDishModalOpen = ref(false);
const quickDishDialogRef = ref(null);
const quickDishNameInputRef = ref(null);

useFocusTrap(dishEditorDialogRef, dishEditorModalOpen);
useFocusTrap(quickDishDialogRef, quickDishModalOpen);
const quickDishErrors = reactive({ category: "", name: "" });
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
  option_groups: [],
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
const categoryLabel = (category) => {
  const superCategoryName = String(category?.super_category_name || "").trim();
  const categoryName = String(category?.name || "").trim();
  if (!superCategoryName || !categoryName) return categoryName || superCategoryName;
  return `${superCategoryName} / ${categoryName}`;
};
const sortedCategoryOptions = computed(() =>
  [...categoryOptions.value].sort(
    (left, right) =>
      String(left?.super_category_name || "").localeCompare(String(right?.super_category_name || "")) ||
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
  dishes
    .filter((dish) => String(dish.category || "") === String(activeCategoryId.value))
    .sort(
      (left, right) =>
        Number(left.position || 0) - Number(right.position || 0) ||
        String(left.name || "").localeCompare(String(right.name || ""))
    )
);
const activeCategoryDishesFiltered = computed(() => {
  const query = dishSearch.value.trim().toLowerCase();
  if (!query) return activeCategoryDishes.value;
  return activeCategoryDishes.value.filter((dish) =>
    [dish.name, dish.description, dish.slug, dish.attributes?.sku, dish.attributes?.barcode, dish.attributes?.brand]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  );
});
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

const renumberDishesForCategory = (categoryId) => {
  const ordered = dishes
    .filter((dish) => String(dish.category || "") === String(categoryId))
    .sort(
      (left, right) =>
        Number(left.position || 0) - Number(right.position || 0) ||
        String(left.name || "").localeCompare(String(right.name || ""))
    );
  ordered.forEach((dish, index) => {
    dish.position = index;
  });
};

const orderedActiveCategoryDishes = computed(() =>
  [...activeCategoryDishes.value].sort(
    (left, right) =>
      Number(left.position || 0) - Number(right.position || 0) ||
      String(left.name || "").localeCompare(String(right.name || ""))
  )
);

const canMoveDishUp = (localId) =>
  orderedActiveCategoryDishes.value.findIndex((dish) => String(dish.local_id) === String(localId)) > 0;
const canMoveDishDown = (localId) => {
  const index = orderedActiveCategoryDishes.value.findIndex((dish) => String(dish.local_id) === String(localId));
  return index > -1 && index < orderedActiveCategoryDishes.value.length - 1;
};

const moveDish = (localId, direction) => {
  const ordered = [...orderedActiveCategoryDishes.value];
  const index = ordered.findIndex((dish) => String(dish.local_id) === String(localId));
  const targetIndex = index + direction;
  if (index < 0 || targetIndex < 0 || targetIndex >= ordered.length) return;
  [ordered[index], ordered[targetIndex]] = [ordered[targetIndex], ordered[index]];
  ordered.forEach((dish, orderedIndex) => {
    dish.position = orderedIndex;
  });
};
const syncActiveCategory = () => {
  if (!sortedCategoryOptions.value.length) {
    activeCategoryId.value = "";
    return;
  }
  // On first load, honour the ?category= query param passed from the categories tab.
  // Only applied when activeCategoryId is not yet set (initial mount), so the user's
  // own dropdown interactions take precedence afterwards.
  if (!activeCategoryId.value) {
    const requested = route?.query?.category;
    if (requested && sortedCategoryOptions.value.some((c) => String(c.id) === String(requested))) {
      activeCategoryId.value = String(requested);
      return;
    }
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
  if (!allowed.has(dishFieldLocales.groupName)) dishFieldLocales.groupName = defaultLocale.value;
  if (!allowed.has(dishFieldLocales.groupOptionName)) dishFieldLocales.groupOptionName = defaultLocale.value;
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

const runDishTranslate = async (dish, field, targetLocale) => {
  if (!dish) return;
  const sourceText = localizedDishFieldValue(dish, field, defaultLocale.value);
  if (!sourceText.trim()) return;
  const key = `${dish.local_id}_${field}`;
  const result = await translateField(key, sourceText, targetLocale, defaultLocale.value);
  if (result) {
    setLocalizedDishFieldValue(dish, field, targetLocale, result);
  } else if (dishTranslateError.value === "notConfigured") {
    toast.show(t("common.translateErrorNotConfigured"), "error");
  } else if (dishTranslateError.value) {
    toast.show(t("common.translateErrorGeneric"), "error");
  }
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

const localizedGroupNameValue = (group, localeCode) => {
  if (!group) return "";
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(group.name || "");
  const map = group.name_i18n;
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};

const setLocalizedGroupNameValue = (group, localeCode, value) => {
  if (!group) return;
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    group.name = nextValue;
  } else {
    if (!group.name_i18n || typeof group.name_i18n !== "object") group.name_i18n = {};
    if (nextValue.trim()) {
      group.name_i18n[locale] = nextValue;
    } else {
      delete group.name_i18n[locale];
    }
  }
};

const localizedGroupOptionNameValue = (opt, localeCode) => {
  if (!opt) return "";
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  if (locale === defaultLocale.value) return String(opt.name || "");
  const map = opt.name_i18n;
  if (!map || typeof map !== "object") return "";
  return String(map[locale] || "");
};

const setLocalizedGroupOptionNameValue = (opt, localeCode, value) => {
  if (!opt) return;
  const locale = normalizeLocale(localeCode || defaultLocale.value);
  const nextValue = String(value || "");
  if (locale === defaultLocale.value) {
    opt.name = nextValue;
  } else {
    if (!opt.name_i18n || typeof opt.name_i18n !== "object") opt.name_i18n = {};
    if (nextValue.trim()) {
      opt.name_i18n[locale] = nextValue;
    } else {
      delete opt.name_i18n[locale];
    }
  }
};

const runQuickDishTranslate = async (field, targetLocale) => {
  const sourceText = localizedQuickDishFieldValue(field, defaultLocale.value);
  if (!sourceText.trim()) return;
  const key = `quick_${field}`;
  const result = await translateField(key, sourceText, targetLocale, defaultLocale.value);
  if (result) {
    setLocalizedQuickDishFieldValue(field, targetLocale, result);
  } else if (dishTranslateError.value === "notConfigured") {
    toast.show(t("common.translateErrorNotConfigured"), "error");
  } else if (dishTranslateError.value) {
    toast.show(t("common.translateErrorGeneric"), "error");
  }
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
  position: Number(option.position || 0),
});

const normalizeGroupOption = (opt = {}) => ({
  id: opt.id,
  local_id: opt.id ? `gopt-${opt.id}` : crypto.randomUUID(),
  name: opt.name || "",
  name_i18n: opt.name_i18n && typeof opt.name_i18n === "object" ? { ...opt.name_i18n } : {},
  price_delta: Number(opt.price_delta || 0),
  position: Number(opt.position || 0),
});

const normalizeOptionGroup = (group = {}) => ({
  id: group.id,
  local_id: group.id ? `group-${group.id}` : crypto.randomUUID(),
  name: group.name || "",
  name_i18n: group.name_i18n && typeof group.name_i18n === "object" ? { ...group.name_i18n } : {},
  min_select: Math.max(0, Number(group.min_select ?? 1)),
  max_select: Math.max(1, Number(group.max_select ?? 1)),
  position: Number(group.position || 0),
  options: Array.isArray(group.options) ? group.options.map(normalizeGroupOption) : [],
});

const WEEKDAYS = [
  { key: "mon" }, { key: "tue" }, { key: "wed" }, { key: "thu" },
  { key: "fri" }, { key: "sat" }, { key: "sun" },
];

const normalizeComboComponents = (list) => {
  if (!Array.isArray(list)) return [];
  return list.map((c) => ({
    component_id: Number(c.component_id),
    name: String(c.name || ""),
    qty: Math.max(1, Number(c.qty) || 1),
    position: Number(c.position || 0),
  }));
};

const normalize = (dish = {}) => ({
  id: dish.id,
  local_id: dish.id || crypto.randomUUID(),
  name: dish.name || "",
  name_i18n: dish.name_i18n && typeof dish.name_i18n === "object" ? { ...dish.name_i18n } : {},
  slug: dish.slug || "",
  category: dish.category ? String(dish.category) : "",
  price: Number(dish.price || 0),
  currency: dish.currency || "MAD",
  image_url: dish.image_url || "",
  description: dish.description || "",
  description_i18n: dish.description_i18n && typeof dish.description_i18n === "object" ? { ...dish.description_i18n } : {},
  position: dish.position ?? dishes.length,
  is_published: dish.is_published ?? true,
  stock_qty: dish.stock_qty != null ? parseInt(dish.stock_qty, 10) : null,
  availability_schedule: dish.availability_schedule || null,
  options: Array.isArray(dish.options) ? dish.options.map((option) => normalizeOption(option)) : [],
  option_groups: Array.isArray(dish.option_groups) ? dish.option_groups.map(normalizeOptionGroup) : [],
  tags: Array.isArray(dish.tags) ? [...dish.tags] : [],
  allergens: Array.isArray(dish.allergens) ? [...dish.allergens] : [],
  attributes: dish.attributes && typeof dish.attributes === "object" ? { ...dish.attributes } : {},
  combo_components: normalizeComboComponents(dish.combo_components),
});

const toggleDishAvailabilitySchedule = (dish, enabled) => {
  if (enabled) {
    dish.availability_schedule = { days: [], time_start: "", time_end: "" };
  } else {
    dish.availability_schedule = null;
  }
};

const toggleAvailabilityDay = (dish, dayKey, checked) => {
  if (!dish.availability_schedule) return;
  const days = Array.isArray(dish.availability_schedule.days) ? [...dish.availability_schedule.days] : [];
  if (checked && !days.includes(dayKey)) {
    dish.availability_schedule.days = [...days, dayKey];
  } else if (!checked) {
    dish.availability_schedule.days = days.filter((d) => d !== dayKey);
  }
};

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
  const cleaned = String(value || "MAD").trim().toUpperCase();
  if (cleaned.length === 3 && /^[A-Z]{3}$/.test(cleaned)) return cleaned;
  return "MAD";
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

const addGroup = (dish) => {
  if (!Array.isArray(dish.option_groups)) dish.option_groups = [];
  dish.option_groups.push(normalizeOptionGroup());
};

const removeGroup = (dish, groupIndex) => {
  if (!Array.isArray(dish.option_groups)) return;
  dish.option_groups.splice(groupIndex, 1);
};

const addGroupOption = (group) => {
  if (!Array.isArray(group.options)) group.options = [];
  group.options.push(normalizeGroupOption());
};

const removeGroupOption = (group, optIdx) => {
  if (!Array.isArray(group.options)) return;
  group.options.splice(optIdx, 1);
};

const canMoveOptionUp = (dish, optIdx) => optIdx > 0;
const canMoveOptionDown = (dish, optIdx) => Array.isArray(dish.options) && optIdx < dish.options.length - 1;
const moveOption = (dish, optIdx, direction) => {
  if (!Array.isArray(dish.options)) return;
  const target = optIdx + direction;
  if (target < 0 || target >= dish.options.length) return;
  [dish.options[optIdx], dish.options[target]] = [dish.options[target], dish.options[optIdx]];
  dish.options.forEach((o, i) => { o.position = i; });
};

const canMoveGroupUp = (dish, groupIdx) => groupIdx > 0;
const canMoveGroupDown = (dish, groupIdx) => Array.isArray(dish.option_groups) && groupIdx < dish.option_groups.length - 1;
const moveGroup = (dish, groupIdx, direction) => {
  if (!Array.isArray(dish.option_groups)) return;
  const target = groupIdx + direction;
  if (target < 0 || target >= dish.option_groups.length) return;
  [dish.option_groups[groupIdx], dish.option_groups[target]] = [dish.option_groups[target], dish.option_groups[groupIdx]];
  dish.option_groups.forEach((g, i) => { g.position = i; });
};

const canMoveGroupOptionUp = (group, optIdx) => optIdx > 0;
const canMoveGroupOptionDown = (group, optIdx) => Array.isArray(group.options) && optIdx < group.options.length - 1;
const moveGroupOption = (group, optIdx, direction) => {
  if (!Array.isArray(group.options)) return;
  const target = optIdx + direction;
  if (target < 0 || target >= group.options.length) return;
  [group.options[optIdx], group.options[target]] = [group.options[target], group.options[optIdx]];
  group.options.forEach((o, i) => { o.position = i; });
};

const toggleTag = (dish, tag, checked) => {
  if (!Array.isArray(dish.tags)) dish.tags = [];
  if (checked) {
    if (!dish.tags.includes(tag)) dish.tags.push(tag);
  } else {
    dish.tags = dish.tags.filter((t) => t !== tag);
  }
};

const toggleAllergen = (dish, allergen, checked) => {
  if (!Array.isArray(dish.allergens)) dish.allergens = [];
  if (checked) {
    if (!dish.allergens.includes(allergen)) dish.allergens.push(allergen);
  } else {
    dish.allergens = dish.allergens.filter((a) => a !== allergen);
  }
};

const publishAllInCategory = async () => {
  const count = activeCategoryDishes.value.length;
  if (!count) return;
  const ok = await confirm({
    title: t("stepDishes.confirmBulkPublish", { count }),
    confirmLabel: t("stepDishes.bulkPublish"),
  });
  if (!ok) return;
  activeCategoryDishes.value.forEach((dish) => { dish.is_published = true; });
};
const unpublishAllInCategory = async () => {
  const count = activeCategoryDishes.value.length;
  if (!count) return;
  const ok = await confirm({
    title: t("stepDishes.confirmBulkUnpublish", { count }),
    confirmLabel: t("stepDishes.bulkUnpublish"),
    danger: true,
  });
  if (!ok) return;
  activeCategoryDishes.value.forEach((dish) => { dish.is_published = false; });
};

const addQuickGroup = () => {
  if (!Array.isArray(quickDish.option_groups)) quickDish.option_groups = [];
  quickDish.option_groups.push(normalizeOptionGroup());
};
const removeQuickGroup = (groupIdx) => {
  if (!Array.isArray(quickDish.option_groups)) return;
  quickDish.option_groups.splice(groupIdx, 1);
};
const addQuickGroupOption = (group) => {
  if (!Array.isArray(group.options)) group.options = [];
  group.options.push(normalizeGroupOption());
};
const removeQuickGroupOption = (group, optIdx) => {
  if (!Array.isArray(group.options)) return;
  group.options.splice(optIdx, 1);
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

// ── Dirty tracking ───────────────────────────────────────────────────────────
// Save used to re-save EVERY dish (PUT + options GET/sync + groups GET/sync =
// 3+ requests each) on every click — 500+ requests on a large menu. Snapshot
// each dish's saved state and only persist rows that actually changed.
const savedSnapshots = new Map(); // local_id → serialized saved state

const dishSnapshot = (dish) => {
  const { local_id, ...rest } = dish; // eslint-disable-line no-unused-vars
  return JSON.stringify(rest);
};

const rememberSaved = (dish) => {
  savedSnapshots.set(dish.local_id, dishSnapshot(dish));
};

const isDishDirty = (dish) =>
  !dish.id || savedSnapshots.get(dish.local_id) !== dishSnapshot(dish);

const allowedTranslationLocalesNow = () =>
  availableContentLocales.value
    .map((locale) => locale.code)
    .filter((locale) => locale !== defaultLocale.value);

// Persist ONE dish (create/update + options sync + option-groups sync) and
// refresh its dirty-tracking snapshot. Throws on failure — callers map the
// error onto the row. Used by the editor-form Save, quick-add, and the
// page-level save loop.
const persistDish = async (dish, allowedTranslationLocales) => {
  const rawAttrs = dish.attributes && typeof dish.attributes === "object" ? dish.attributes : {};
  const cleanedAttrs = Object.fromEntries(
    Object.entries(rawAttrs)
      .map(([k, v]) => [k, typeof v === "string" ? v.trim() : v])
      .filter(([, v]) => v !== "" && v != null)
  );
  const saved = await dishApi.upsert({
    ...dish,
    category: Number(dish.category) || dish.category,
    price: Number(dish.price) || 0,
    currency: normalizeCurrency(dish.currency),
    name_i18n: pickI18nMap(dish.name_i18n, allowedTranslationLocales),
    description_i18n: pickI18nMap(dish.description_i18n, allowedTranslationLocales),
    attributes: cleanedAttrs,
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

  const desiredGroups = Array.isArray(dish.option_groups) ? dish.option_groups : [];
  const savedGroups = await optionGroupApi.syncForDish(
    dish.id,
    desiredGroups.map((group) => ({
      ...group,
      name_i18n: pickI18nMap(group.name_i18n, allowedTranslationLocales),
      options: (group.options || []).map((opt) => ({
        ...opt,
        name_i18n: pickI18nMap(opt.name_i18n, allowedTranslationLocales),
      })),
    }))
  );
  dish.option_groups = savedGroups.map(normalizeOptionGroup);
  // Snapshot the post-save state so an unchanged row is skipped next time.
  rememberSaved(dish);
};

// OPS-5: surface plan-limit errors with a clear "upgrade your plan" message.
// dishApi.upsert wraps the axios error and keeps the original on `.raw`, so the
// backend `code` ("dish_limit_reached") is reachable there.
const isDishLimitError = (err) =>
  err?.raw?.response?.data?.code === "dish_limit_reached";

const showDishSaveError = (err) => {
  if (isDishLimitError(err)) {
    toast.show(t("stepDishes.dishLimitReached"), "error");
    return true;
  }
  return false;
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
    savedSnapshots.clear();
    rows.forEach(rememberSaved);
  } catch {
    status.value = t("common.loadFailed");
    dishes.splice(0, dishes.length);
    savedSnapshots.clear();
  }
  syncActiveCategory();
};

const setActiveCategory = (categoryId) => {
  activeCategoryId.value = String(categoryId || "");
  dishSearch.value = "";
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

// Form-level save: persist ONLY the dish open in the editor dialog.
const savingDishNow = ref(false);
const saveDishNow = async () => {
  const dish = editingDish.value;
  if (!dish || savingDishNow.value) return;
  if (String(dish.name || "").trim().length < 2) {
    setRowError(dish.local_id, "name", t("stepDishes.nameMin"));
    toast.show(t("stepDishes.fixValidation"), "error");
    return;
  }
  if (!dish.category) {
    setRowError(dish.local_id, "category", t("stepDishes.selectCategoryError"));
    toast.show(t("stepDishes.fixValidation"), "error");
    return;
  }
  savingDishNow.value = true;
  try {
    await persistDish(dish, allowedTranslationLocalesNow());
    delete rowErrors[dish.local_id];
    toast.show(t("stepDishes.savedToast"), "success");
    closeDishEditor();
  } catch (e) {
    if (isDishLimitError(e)) {
      setRowError(dish.local_id, "options", t("stepDishes.dishLimitReached"));
      toast.show(t("stepDishes.dishLimitReached"), "error");
    } else {
      mapServerErrorsToRow(dish.local_id, e?.fieldErrors || {});
      if (e?.message) setRowError(dish.local_id, "options", e.message);
      toast.show(e?.message || t("stepDishes.saveFailed"), "error");
    }
  } finally {
    savingDishNow.value = false;
  }
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
  quickDish.option_groups = [];
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
  quickDishErrors.category = "";
  quickDishErrors.name = "";
  quickDishModalOpen.value = true;
  nextTick(() => quickDishNameInputRef.value?.focus());
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

const quickAddDish = async () => {
  quickDishErrors.category = "";
  quickDishErrors.name = "";
  const name = String(quickDish.name || "").trim();
  const category = resolveQuickDishCategory(quickDish.category);
  const allowedTranslationLocales = availableContentLocales.value
    .map((locale) => locale.code)
    .filter((locale) => locale !== defaultLocale.value);
  if (!category) {
    quickDishErrors.category = t("stepDishes.selectCategoryError");
    return;
  }
  if (name.length < 2) {
    quickDishErrors.name = t("stepDishes.nameMin");
    nextTick(() => quickDishNameInputRef.value?.focus());
    return;
  }
  const row = normalize({
    category,
    name,
    name_i18n: pickI18nMap(quickDish.name_i18n, allowedTranslationLocales),
    description: String(quickDish.description || "").trim(),
    description_i18n: pickI18nMap(quickDish.description_i18n, allowedTranslationLocales),
    price: Number(quickDish.price) || 0,
    image_url: String(quickDish.image_url || "").trim(),
    position: activeCategoryDishes.value.length,
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
    option_groups: (Array.isArray(quickDish.option_groups) ? quickDish.option_groups : [])
      .map(normalizeOptionGroup)
      .filter((g) => String(g.name || "").trim()),
  });
  dishes.push(row);
  setActiveCategory(category);
  renumberDishesForCategory(category);
  closeQuickDishModal();
  // Persist the new dish immediately (form-level save). On failure the row
  // stays local and dirty — the page-level Save will retry it.
  try {
    await persistDish(row, allowedTranslationLocales);
    toast.show(t("stepDishes.savedToast"), "success");
  } catch (e) {
    if (showDishSaveError(e)) {
      setRowError(row.local_id, "options", t("stepDishes.dishLimitReached"));
    } else {
      mapServerErrorsToRow(row.local_id, e?.fieldErrors || {});
      toast.show(e?.message || t("stepDishes.saveFailed"), "error");
    }
  }
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
  if (dish?.category) {
    renumberDishesForCategory(dish.category);
  }
};

const cloneDish = (localId) => {
  const original = dishes.find((d) => d.local_id === localId);
  if (!original) return;
  const clone = normalize({
    ...original,
    id: undefined,                        // new dish — no backend id yet
    name: t("stepDishes.cloneDishName", { name: original.name || t("stepDishes.dishNamePlaceholder") }),
    name_i18n: {},                        // don't copy translations — name changed
    slug: "",                             // auto-generated on save
    options: original.options.map((o) => ({ ...o, id: undefined, local_id: crypto.randomUUID() })),
    option_groups: original.option_groups.map((g) => ({
      ...g,
      id: undefined,
      local_id: crypto.randomUUID(),
      options: (g.options || []).map((o) => ({ ...o, id: undefined, local_id: crypto.randomUUID() })),
    })),
  });
  // Insert right after the original
  const idx = dishes.findIndex((d) => d.local_id === localId);
  dishes.splice(idx + 1, 0, clone);
  // Open the editor so the owner can tweak before saving
  nextTick(() => openDishEditor(clone.local_id));
};

// ── Combo builder ─────────────────────────────────────────────────────────────
const comboPicker = reactive({}); // localId -> selected component id string

/** Dishes that are valid as combo components for the given dish (no combos, no self, has id) */
const availableComboComponents = (dish) => {
  const existingIds = new Set((dish.combo_components || []).map((c) => c.component_id));
  return dishes.filter(
    (d) =>
      d.id &&
      d.id !== dish.id &&
      !existingIds.has(d.id) &&
      (!Array.isArray(d.combo_components) || d.combo_components.length === 0)
  );
};

/** Sum of component prices using the current loaded dish list */
const comboComponentsTotal = (dish) => {
  let total = 0;
  for (const comp of dish.combo_components || []) {
    const found = dishes.find((d) => d.id === comp.component_id);
    if (found) total += Number(found.price || 0) * comp.qty;
  }
  return total;
};

/** How much the combo saves vs buying components individually */
const comboSavings = (dish) => {
  const componentTotal = comboComponentsTotal(dish);
  const comboPrice = Number(dish.price || 0);
  return componentTotal > comboPrice ? componentTotal - comboPrice : 0;
};

const toggleComboMode = (dish, enabled) => {
  if (!dish) return;
  if (!enabled) {
    dish.combo_components = [];
    delete comboPicker[dish.local_id];
  } else {
    if (!Array.isArray(dish.combo_components)) dish.combo_components = [];
    comboPicker[dish.local_id] = "";
  }
};

const addComboComponent = (dish) => {
  const idStr = comboPicker[dish.local_id];
  if (!idStr) return;
  const id = Number(idStr);
  const found = dishes.find((d) => d.id === id);
  if (!found) return;
  if (!Array.isArray(dish.combo_components)) dish.combo_components = [];
  if (dish.combo_components.length >= 8) return;
  if (found.combo_components?.length) {
    toast.show(t("combos.nestingError"), "error");
    return;
  }
  if (dish.combo_components.some((c) => c.component_id === id)) return;
  dish.combo_components.push({ component_id: id, name: found.name, qty: 1, position: dish.combo_components.length });
  comboPicker[dish.local_id] = "";
};

const removeComboComponent = (dish, idx) => {
  if (!Array.isArray(dish.combo_components)) return;
  dish.combo_components.splice(idx, 1);
};

const removeDishByLocalId = async (localId) => {
  const dish = dishes.find((d) => d.local_id === localId);
  const ok = await confirm({
    title: t("stepDishes.confirmRemoveDish", { name: dish?.name || t("common.thisDish") }),
    body: t("confirmModal.defaultBody"),
    confirmLabel: t("common.delete"),
  });
  if (!ok) return;
  const index = dishes.findIndex((d) => d.local_id === localId);
  if (index < 0) return;
  // If the dish has a backend id, attempt the delete first so we catch 409 early.
  if (dish?.id) {
    try {
      await dishApi.remove(dish.id);
    } catch (e) {
      if (e?.status === 409 || e?.raw?.response?.status === 409) {
        toast.show(t("combos.protectedDelete"), "error");
        return;
      }
      toast.show(e?.message || t("common.saveFailed"), "error");
      return;
    }
    // Remove from removedIds if it was queued (shouldn't be, but guard)
    removedIds.value = removedIds.value.filter((id) => id !== dish.id);
    dishes.splice(index, 1);
    if (dish.category) renumberDishesForCategory(dish.category);
    queueCleanup(dish.image_url || "");
    delete rowErrors[dish.local_id];
    delete uploadingRows[dish.local_id];
    delete uploadProgressRows[dish.local_id];
    delete draggingRows[dish.local_id];
    if (String(dishEditorLocalId.value) === String(dish.local_id)) closeDishEditor();
  } else {
    await remove(index);
  }
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
  globalError.value = "";
  if (!validateClient()) {
    status.value = t("stepDishes.fixValidation");
    saving.value = false;
    return;
  }
  try {
    const validDishes = dishes.filter((d) => d.name?.trim() && d.category);
    // Only persist rows that changed since load / last save — re-saving the
    // whole menu fired hundreds of requests on large menus.
    const dirtyDishes = validDishes.filter(isDishDirty);
    const allowedTranslationLocales = availableContentLocales.value
      .map((locale) => locale.code)
      .filter((locale) => locale !== defaultLocale.value);
    for (const dish of dirtyDishes) {
      try {
        await persistDish(dish, allowedTranslationLocales);
      } catch (e) {
        if (isDishLimitError(e)) {
          setRowError(dish.local_id, "options", t("stepDishes.dishLimitReached"));
        } else {
          mapServerErrorsToRow(dish.local_id, e?.fieldErrors || {});
          if (e?.message) {
            setRowError(dish.local_id, "options", e.message);
          }
        }
        throw e;
      }
    }
    for (const id of removedIds.value) {
      try {
        await dishApi.remove(id);
      } catch (e) {
        if (e?.status === 409 || e?.raw?.response?.status === 409) {
          toast.show(t("combos.protectedDelete"), "error");
          continue;
        }
        throw e;
      }
    }
    await flushPendingCleanup();
    removedIds.value = [];
    status.value = t("common.saved");
    toast.show(t("stepDishes.savedToast"), "success");
    if (!props.standalone) emit("next");
  } catch (e) {
    status.value = t("common.saveFailed");
    globalError.value = isDishLimitError(e) ? t("stepDishes.dishLimitReached") : (e?.message || t("stepDishes.saveFailed"));
    toast.show(globalError.value, "error");
  } finally {
    saving.value = false;
  }
};

// ── Bulk price adjustment ─────────────────────────────────────────────────────
const bulkPriceModalOpen = ref(false);
const bulkPriceDialogRef = ref(null);
const bulkPriceAction = ref("increase_percent");
const bulkPriceValue = ref("");
const bulkPriceCategoryId = ref("");   // "" = all categories
const bulkPriceRoundTo = ref(0);
const bulkPricePreview = ref([]);
const bulkPriceLoading = ref(false);
const bulkPriceApplying = ref(false);
const bulkPriceError = ref("");

useFocusTrap(bulkPriceDialogRef, bulkPriceModalOpen);

const isPercentAction = computed(() =>
  bulkPriceAction.value === "increase_percent" || bulkPriceAction.value === "decrease_percent"
);

const openBulkPriceModal = () => {
  bulkPriceAction.value = "increase_percent";
  bulkPriceValue.value = "";
  bulkPriceCategoryId.value = activeCategoryId.value || "";
  bulkPriceRoundTo.value = 0;
  bulkPricePreview.value = [];
  bulkPriceError.value = "";
  bulkPriceModalOpen.value = true;
};

const closeBulkPriceModal = () => {
  bulkPriceModalOpen.value = false;
};

const buildBulkPricePayload = (dryRun) => {
  const v = parseFloat(bulkPriceValue.value);
  const payload = { action: bulkPriceAction.value, value: v, dry_run: dryRun };
  if (bulkPriceCategoryId.value) payload.category_id = Number(bulkPriceCategoryId.value);
  if (bulkPriceRoundTo.value) payload.round_to = bulkPriceRoundTo.value;
  return payload;
};

const previewBulkPrice = async () => {
  const v = parseFloat(bulkPriceValue.value);
  if (!v || v <= 0) {
    bulkPriceError.value = t("stepDishes.bulkPriceValueError");
    return;
  }
  bulkPriceError.value = "";
  bulkPriceLoading.value = true;
  try {
    const { data } = await api.patch("/owner/dishes/bulk-price/", buildBulkPricePayload(true));
    bulkPricePreview.value = data.items || [];
  } catch (err) {
    bulkPriceError.value = err?.response?.data?.detail || t("stepDishes.bulkPriceError");
    bulkPricePreview.value = [];
  } finally {
    bulkPriceLoading.value = false;
  }
};

const applyBulkPrice = async () => {
  const v = parseFloat(bulkPriceValue.value);
  if (!v || v <= 0) {
    bulkPriceError.value = t("stepDishes.bulkPriceValueError");
    return;
  }
  bulkPriceError.value = "";
  bulkPriceApplying.value = true;
  try {
    const { data } = await api.patch("/owner/dishes/bulk-price/", buildBulkPricePayload(false));
    const count = data.updated || 0;
    toast.show(t("stepDishes.bulkPriceApplied", { count }), "success");
    closeBulkPriceModal();
    // Reload local dish list so prices reflect the update
    await load();
  } catch (err) {
    bulkPriceError.value = err?.response?.data?.detail || t("stepDishes.bulkPriceError");
  } finally {
    bulkPriceApplying.value = false;
  }
};

const onModalEscape = (e) => {
  if (e.key !== "Escape") return;
  if (bulkPriceModalOpen.value) closeBulkPriceModal();
  else if (quickDishModalOpen.value) closeQuickDishModal();
  else if (dishEditorModalOpen.value) closeDishEditor();
};
onMounted(load);
onMounted(() => document.addEventListener("keydown", onModalEscape));
onUnmounted(() => document.removeEventListener("keydown", onModalEscape));
</script>












