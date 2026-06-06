<template>
  <div class="ui-panel space-y-5 p-5">
    <section class="ui-section-band ui-reveal space-y-4 rounded-[26px] p-4 sm:p-5">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("stepSuperCategories.title") }}</p>
          <div class="space-y-1">
            <h2 class="text-xl font-semibold text-white sm:text-2xl">{{ t("stepSuperCategories.heading") }}</h2>
            <p class="max-w-2xl text-sm text-slate-300">{{ t("stepSuperCategories.description") }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <span class="ui-status-pill">
              <AppIcon name="filter" class="h-3.5 w-3.5" aria-hidden="true" />
              <span class="tabular-nums">{{ rows.length }}</span> {{ t("stepSuperCategories.heading") }}
            </span>
            <span class="ui-status-pill">
              <AppIcon name="check" class="h-3.5 w-3.5" aria-hidden="true" />
              <span class="tabular-nums">{{ enabledCount }}</span> {{ t("stepSuperCategories.enabledSummary") }}
            </span>
            <span class="ui-status-pill">
              <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
              <span class="tabular-nums">{{ disabledCount }}</span> {{ t("stepSuperCategories.disabled") }}
            </span>
          </div>
        </div>

        <div class="flex flex-wrap gap-2 lg:justify-end">
          <button class="ui-btn-outline gap-2 px-4 py-2 text-sm" type="button" :disabled="saving" @click="saveAll">
            <AppIcon :name="saving ? 'refresh' : 'check'" class="h-4 w-4" aria-hidden="true" />
            {{ saving ? t("common.saving") : t("common.save") }}
          </button>
          <button class="ui-btn-primary gap-2 px-4 py-2 text-sm" type="button" @click="openQuickModal">
            <AppIcon name="plus" class="h-4 w-4" aria-hidden="true" />
            {{ t("stepSuperCategories.add") }}
          </button>
        </div>
      </div>

      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="ui-metric-card ps-5">
          <p class="ui-stat-label">{{ t("stepSuperCategories.title") }}</p>
          <p class="ui-stat-value tabular-nums text-2xl">{{ rows.length }}</p>
          <p class="ui-stat-note">{{ t("stepSuperCategories.heading") }}</p>
        </div>
        <div class="ui-metric-card ps-5">
          <p class="ui-stat-label">{{ t("stepSuperCategories.enabled") }}</p>
          <p class="ui-stat-value tabular-nums text-2xl">{{ enabledCount }}</p>
          <p class="ui-stat-note">{{ t("stepSuperCategories.enabledSummary") }}</p>
        </div>
        <div class="ui-metric-card ps-5">
          <p class="ui-stat-label">{{ t("stepSuperCategories.disabled") }}</p>
          <p class="ui-stat-value tabular-nums text-2xl">{{ disabledCount }}</p>
          <p class="ui-stat-note">{{ t("stepSuperCategories.disableToggle") }}</p>
        </div>
        <div class="ui-metric-card ps-5">
          <p class="ui-stat-label">{{ t("common.categories") }}</p>
          <p class="ui-stat-value tabular-nums text-2xl">{{ categoriesTotal }}</p>
          <p class="ui-stat-note">{{ t("common.categories") }} {{ t("common.available") }}</p>
        </div>
      </div>

      <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <label class="space-y-1 text-sm text-slate-300">
          <span class="sr-only">{{ t("common.search") }}</span>
          <div class="relative">
            <AppIcon name="search" class="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
            <input v-model.trim="search" type="search" class="ui-input ps-10" enterkeyhint="search" :placeholder="t('common.search')" />
          </div>
        </label>
        <div class="min-w-0">
          <div class="ui-scroll-row">
            <span class="ui-data-strip tabular-nums">{{ filteredRows.length }} / {{ rows.length }}</span>
            <span class="ui-data-strip"><span class="tabular-nums">{{ enabledCount }}</span> {{ t("stepSuperCategories.enabledSummary") }}</span>
            <span class="ui-data-strip tabular-nums">{{ categoriesTotal }} {{ t("common.categories") }}</span>
          </div>
        </div>
      </div>
    </section>

    <ul class="space-y-3 list-none p-0">
      <li v-if="!filteredRows.length" class="list-none"><div
        class="ui-empty-state flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"
      >
        <div class="relative z-10 flex items-start gap-3">
          <span class="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-slate-700/70 bg-slate-900/75 text-[var(--color-secondary)] shadow-lg shadow-black/25">
            <AppIcon :name="search ? 'search' : 'filter'" class="h-5 w-5" aria-hidden="true" />
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
          <AppIcon name="plus" class="h-4 w-4" aria-hidden="true" />
          {{ t("stepSuperCategories.add") }}
        </button>
      </div></li>

      <li
        v-for="(row, index) in filteredRows"
        :key="row.local_id"
        class="list-none"
      ><article
        class="ui-selection-card ui-surface-lift ui-reveal flex items-center gap-2.5 p-2.5 sm:gap-3"
        :data-warning="row.is_temporarily_disabled"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms`, 'content-visibility': 'auto', 'contain-intrinsic-size': 'auto 64px' }"
      >
        <!-- Reorder: stacked chevrons -->
        <div class="flex shrink-0 flex-col gap-0.5">
          <button
            class="ui-press ui-touch-target flex items-center justify-center rounded text-slate-500 transition hover:text-white disabled:pointer-events-none disabled:opacity-20"
            type="button" :disabled="!canMoveUp(row.local_id)" :aria-label="t('common.moveUp')"
            @click="moveRow(row.local_id, -1)"
          >
            <AppIcon name="chevronUp" class="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            class="ui-press ui-touch-target flex items-center justify-center rounded text-slate-500 transition hover:text-white disabled:pointer-events-none disabled:opacity-20"
            type="button" :disabled="!canMoveDown(row.local_id)" :aria-label="t('common.moveDown')"
            @click="moveRow(row.local_id, 1)"
          >
            <AppIcon name="chevronDown" class="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <!-- Name + slug + meta — the whole block drills into this group's categories (pencil edits) -->
        <button type="button" class="flex min-w-0 flex-1 items-center gap-2 text-left" :aria-label="t('stepSuperCategories.openCategories')" @click="drillIn(row)">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span
                class="h-1.5 w-1.5 shrink-0 rounded-full"
                :class="(row.is_published && !row.is_temporarily_disabled) ? 'bg-emerald-400' : 'bg-slate-600'"
                aria-hidden="true"
              />
              <h3 class="truncate text-sm font-semibold text-white">{{ row.name || t("stepSuperCategories.namePlaceholder") }}</h3>
              <span class="ui-route-badge shrink-0">{{ row.slug || 'draft' }}</span>
            </div>
            <div class="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
              <span :class="row.is_temporarily_disabled ? 'text-amber-300' : ''">
                {{ row.is_temporarily_disabled ? t("stepSuperCategories.disabled") : (row.is_published ? t("stepSuperCategories.enabled") : t("common.soon")) }}
              </span>
              <span aria-hidden="true">·</span>
              <span class="tabular-nums">{{ Number(row.category_count || 0) }}</span>
              <span>{{ t("common.categories") }}</span>
            </div>
          </div>
          <AppIcon name="chevronRight" class="h-4 w-4 shrink-0 text-slate-500 rtl:scale-x-[-1]" aria-hidden="true" />
        </button>

        <!-- Actions: edit · delete (delete blocked while it still holds categories) -->
        <div class="flex shrink-0 items-center gap-1.5">
          <button
            class="ui-press flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700 text-slate-300 transition hover:border-slate-500 hover:text-white"
            type="button" :aria-label="t('common.edit')" @click="openEditor(row.local_id)"
          >
            <AppIcon name="pencil" class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button
            class="ui-press flex h-8 w-8 items-center justify-center rounded-lg border border-red-400/25 text-red-300 transition hover:border-red-400/50 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-40"
            type="button"
            :disabled="Number(row.category_count || 0) > 0"
            :title="Number(row.category_count || 0) > 0 ? t('common.categories') : t('common.remove')"
            :aria-label="Number(row.category_count || 0) > 0 ? t('common.categories') : t('common.remove')"
            @click="removeByLocalId(row.local_id)"
          >
            <AppIcon name="trash" class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      </article></li>
    </ul>

    <Teleport to="body">
      <div
        v-if="editorOpen && editingRow"
        class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        @click.self="closeEditor"
      >
        <div ref="editorDialogRef" role="dialog" aria-modal="true" aria-labelledby="step-super-categories-editor-dialog-title" class="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4 sm:px-5">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("stepSuperCategories.title") }}</p>
              <h3 id="step-super-categories-editor-dialog-title" class="text-lg font-semibold text-white">{{ t("stepSuperCategories.edit") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline gap-2 px-3 py-1.5 text-xs" @click="closeEditor">
              <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
              {{ t("common.close") }}
            </button>
          </div>

          <div class="space-y-4 px-4 pt-4 pb-5 sm:px-5 sm:pt-5">
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
                      :aria-pressed="fieldLocales.name === locale.code"
                      class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      :class="fieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                      @click="fieldLocales.name = locale.code"
                    >
                      {{ locale.nativeLabel }}
                    </button>
                  </div>
                </div>
                <input
                  type="text"
                  :value="localizedFieldValue(editingRow, 'name', fieldLocales.name)"
                  class="ui-input"
                  :placeholder="t('stepSuperCategories.namePlaceholder')"
                  :aria-label="t('stepSuperCategories.namePlaceholder')"
                  :aria-invalid="rowError(editingRow, 'name') ? 'true' : undefined"
                  :aria-describedby="rowError(editingRow, 'name') ? `step-supcat-name-error-${editingRow.local_id}` : undefined"
                  @input="setLocalizedFieldValue(editingRow, 'name', fieldLocales.name, $event.target.value)"
                />
                <p v-if="rowError(editingRow, 'name')" :id="`step-supcat-name-error-${editingRow.local_id}`" role="alert" class="text-xs text-red-300">{{ rowError(editingRow, 'name') }}</p>
              </div>

              <!-- Description (tagline for menu-selector card) -->
              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepSuperCategories.descriptionLabel") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`super-desc-${locale.code}`"
                      type="button"
                      :aria-pressed="fieldLocales.description === locale.code"
                      class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      :class="fieldLocales.description === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                      @click="fieldLocales.description = locale.code"
                    >{{ locale.nativeLabel }}</button>
                  </div>
                </div>
                <input
                  type="text"
                  :value="localizedFieldValue(editingRow, 'description', fieldLocales.description)"
                  class="ui-input"
                  :aria-label="t('stepSuperCategories.descriptionLabel')"
                  :placeholder="t('stepSuperCategories.descriptionPlaceholder')"
                  maxlength="280"
                  @input="setLocalizedFieldValue(editingRow, 'description', fieldLocales.description, $event.target.value)"
                />
                <p class="text-[11px] text-slate-500">{{ t("stepSuperCategories.descriptionHint") }}</p>
              </div>

              <!-- Cover image URL -->
              <div class="space-y-1">
                <p class="text-xs text-slate-400">{{ t("stepSuperCategories.imageUrlLabel") }}</p>
                <input
                  v-model.trim="editingRow.image_url"
                  class="ui-input"
                  type="url"
                  :aria-label="t('stepSuperCategories.imageUrlLabel')"
                  :placeholder="t('stepSuperCategories.imageUrlPlaceholder')"
                />
                <p class="text-[11px] text-slate-500">{{ t("stepSuperCategories.imageUrlHint") }}</p>
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

          <div class="sticky bottom-0 z-10 flex justify-end border-t border-slate-800 bg-slate-950/95 px-4 py-4 sm:px-5">
            <button type="button" class="ui-btn-primary gap-2 px-4 py-2 text-sm" @click="closeEditor">
              <AppIcon name="check" class="h-4 w-4" aria-hidden="true" />
              {{ t("common.done") }}
            </button>
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
        <div ref="quickDialogRef" role="dialog" aria-modal="true" aria-labelledby="step-super-categories-quick-dialog-title" class="w-full max-w-2xl rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("stepSuperCategories.title") }}</p>
              <h3 id="step-super-categories-quick-dialog-title" class="text-lg font-semibold text-white">{{ t("stepSuperCategories.add") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline gap-2 px-3 py-1.5 text-xs" @click="closeQuickModal">
              <AppIcon name="close" class="h-3.5 w-3.5" aria-hidden="true" />
              {{ t("common.close") }}
            </button>
          </div>
          <div class="space-y-4 p-4">
            <div class="ui-scroll-row">
              <span class="ui-data-strip"><AppIcon name="plus" class="h-3.5 w-3.5" aria-hidden="true" />{{ t("stepSuperCategories.heading") }}</span>
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
                      :aria-pressed="quickFieldLocales.name === locale.code"
                      class="rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors"
                      :class="quickFieldLocales.name === locale.code ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
                      @click="quickFieldLocales.name = locale.code"
                    >
                      {{ locale.nativeLabel }}
                    </button>
                  </div>
                </div>
                <input
                  ref="quickNameInputRef"
                  type="text"
                  :value="localizedQuickFieldValue('name', quickFieldLocales.name)"
                  class="ui-input"
                  :class="quickAddError ? 'border-red-400' : ''"
                  :placeholder="t('stepSuperCategories.namePlaceholder')"
                  :aria-label="t('stepSuperCategories.namePlaceholder')"
                  :aria-invalid="quickAddError ? 'true' : undefined"
                  :aria-describedby="quickAddError ? 'step-supcat-quick-name-error' : undefined"
                  @input="setLocalizedQuickFieldValue('name', quickFieldLocales.name, $event.target.value); quickAddError = ''"
                />
                <p v-if="quickAddError" id="step-supcat-quick-name-error" role="alert" class="text-xs text-red-300 mt-1">{{ quickAddError }}</p>
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <label class="space-y-1 text-sm text-slate-300">
                  <span class="text-xs text-slate-400">{{ t("stepSuperCategories.position") }}</span>
                  <input v-model.number="quickRow.position" type="number" min="0" class="ui-input" :placeholder="t('stepSuperCategories.position')" />
                </label>
                <label class="space-y-1 text-sm text-slate-300">
                  <span class="text-xs text-slate-400">{{ t("stepSuperCategories.visibility") }}</span>
                  <select v-model="quickRow.is_published" class="ui-input">
                    <option :value="true">{{ t("common.available") }}</option>
                    <option :value="false">{{ t("common.soon") }}</option>
                  </select>
                </label>
              </div>

              <label class="inline-flex items-center gap-2 text-sm text-slate-200">
                <input v-model="quickRow.is_temporarily_disabled" type="checkbox" class="h-4 w-4 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
                {{ t("stepSuperCategories.disableToggle") }}
              </label>

              <textarea
                v-model.trim="quickRow.disabled_note"
                rows="3"
                class="ui-textarea"
                :aria-label="t('stepSuperCategories.disabledNote')"
                :placeholder="t('stepSuperCategories.disabledNotePlaceholder')"
              ></textarea>
            </div>
          </div>
          <div class="sticky bottom-0 z-10 flex justify-end gap-2 border-t border-slate-800 bg-slate-950/95 px-4 py-4">
            <button type="button" class="ui-btn-outline gap-2 px-4 py-2 text-sm" @click="closeQuickModal">
              <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
              {{ t("common.close") }}
            </button>
            <button type="button" class="ui-btn-primary gap-2 px-4 py-2 text-sm" @click="quickAdd">
              <AppIcon name="plus" class="h-4 w-4" aria-hidden="true" />
              {{ t("stepSuperCategories.add") }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <div v-if="globalError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-red-300">{{ globalError }}</p>
    </div>

    <div class="ui-toolbar-band flex flex-wrap items-center justify-between gap-3 border-t border-slate-800/80 pt-3">
      <div class="flex flex-wrap gap-2 text-xs text-slate-400">
        <span class="ui-data-strip tabular-nums">{{ rows.length }} {{ t("stepSuperCategories.heading") }}</span>
        <span class="ui-data-strip tabular-nums">{{ enabledCount }} {{ t("stepSuperCategories.enabledSummary") }}</span>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <p class="text-sm text-slate-400">{{ status }}</p>
        <button class="ui-btn-outline gap-2 px-4 py-2 text-sm" :disabled="saving" @click="saveAll">
          <AppIcon :name="saving ? 'refresh' : 'check'" class="h-4 w-4" aria-hidden="true" />
          {{ saving ? t("common.saving") : t("common.save") }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { superCategoryApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { useFocusTrap } from "../composables/useFocusTrap";
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
const quickNameInputRef = ref(null);
const quickAddError = ref("");
const editorOpen = ref(false);
const editorDialogRef = ref(null);
const quickDialogRef  = ref(null);
useFocusTrap(editorDialogRef, editorOpen);
useFocusTrap(quickDialogRef, quickModalOpen);
const editorLocalId = ref("");
const tenant = useTenantStore();
const toast = useToastStore();
const { t } = useI18n();
const router = useRouter();

// Clicking a super-category row drills into its categories (the pencil edits it).
// Unsaved drafts have no id yet — fall back to opening the editor.
const drillIn = (row) => {
  if (!row?.id) {
    openEditor(row.local_id);
    return;
  }
  router.push({ name: "owner-menu-builder", query: { tab: "categories", super: String(row.id) } });
};

const fieldLocales = reactive({ name: "en", description: "en" });
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
  if (!allowed.has(fieldLocales.description)) fieldLocales.description = defaultLocale.value;
  if (!allowed.has(quickFieldLocales.name)) quickFieldLocales.name = defaultLocale.value;
};
watch([availableContentLocales, defaultLocale], syncFieldLocales, { immediate: true });

const normalizeRow = (row = {}) => ({
  id: row.id,
  local_id: row.id || crypto.randomUUID(),
  name: row.name || "",
  name_i18n: row.name_i18n && typeof row.name_i18n === "object" ? { ...row.name_i18n } : {},
  slug: row.slug || "",
  description: row.description || "",
  description_i18n: row.description_i18n && typeof row.description_i18n === "object" ? { ...row.description_i18n } : {},
  image_url: row.image_url || "",
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
  quickAddError.value = "";
  quickModalOpen.value = true;
  nextTick(() => quickNameInputRef.value?.focus());
};
const closeQuickModal = () => {
  quickModalOpen.value = false;
};

const quickAdd = () => {
  const name = String(quickRow.name || "").trim();
  if (name.length < 2) {
    quickAddError.value = t("stepSuperCategories.nameMin");
    return;
  }
  quickAddError.value = "";
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

const onModalEscape = (e) => {
  if (e.key !== "Escape") return;
  if (quickModalOpen.value) closeQuickModal();
  else if (editorOpen.value) closeEditor();
};
onMounted(load);
onMounted(() => document.addEventListener("keydown", onModalEscape));
onUnmounted(() => document.removeEventListener("keydown", onModalEscape));
</script>


