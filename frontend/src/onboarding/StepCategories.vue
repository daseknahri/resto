<template>
  <div class="ui-panel space-y-5 p-5">
    <section class="ui-section-band ui-reveal space-y-4 rounded-[26px] p-4 sm:p-5">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div class="space-y-1">
          <p class="ui-kicker">{{ t("stepCategories.title") }}</p>
          <h2 class="text-xl font-semibold text-white sm:text-2xl">{{ t("common.categories") }}</h2>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="ui-btn-outline gap-2 px-4 py-2 text-sm" type="button" :disabled="saving || !superCategoryOptions.length" @click="saveAll">
            <AppIcon :name="saving ? 'refresh' : 'check'" class="h-4 w-4" aria-hidden="true" />
            {{ saving ? t("common.saving") : t("common.save") }}
          </button>
          <button class="ui-btn-outline gap-2 px-4 py-2 text-sm" type="button" :disabled="!superCategoryOptions.length" @click="openQuickModal">
            <AppIcon name="plus" class="h-4 w-4" aria-hidden="true" />
            {{ t("stepCategories.addCategory") }}
          </button>
        </div>
      </div>

      <div v-if="!superCategoryOptions.length" class="ui-empty-state flex flex-col items-start gap-3 p-5 sm:flex-row sm:items-center">
        <span class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-amber-400/30 bg-amber-500/10 text-amber-300 shadow-lg shadow-black/20">
          <AppIcon name="info" class="h-5 w-5" aria-hidden="true" />
        </span>
        <p class="relative z-10 text-sm text-amber-100">{{ t("stepCategories.addSuperCategoriesFirst") }}</p>
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
            <input v-model.trim="search" type="search" class="ui-input border-slate-700 bg-slate-950/70" enterkeyhint="search" :placeholder="t('common.search')" />
          </label>
          <div class="min-w-0">
            <div class="ui-scroll-row">
              <span class="ui-data-strip">{{ filteredCategories.length }} / {{ activeCategories.length }} {{ t("common.categories") }}</span>
              <span class="ui-data-strip">{{ activeSuperCategoryRecord?.name || '' }}</span>
            </div>
          </div>
        </div>
      </template>
    </section>

    <ul class="space-y-3 list-none">
      <li v-if="superCategoryOptions.length && !filteredCategories.length">
        <div
          class="ui-empty-state flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"
        >
          <div class="relative z-10 flex items-start gap-3">
            <span class="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-slate-700/70 bg-slate-900/75 text-[var(--color-secondary)] shadow-lg shadow-black/25">
              <AppIcon :name="search ? 'search' : 'filter'" class="h-5 w-5" aria-hidden="true" />
            </span>
            <div class="space-y-1">
              <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ t("stepCategories.title") }}</p>
              <h3 class="text-base font-semibold text-white">{{ search ? t("common.search") : t("stepCategories.addAtLeastOne") }}</h3>
              <p class="max-w-xl text-sm text-slate-400">
                {{ search ? `${t("common.search")} - 0` : t("stepCategories.description") }}
              </p>
            </div>
          </div>
          <button v-if="!search" class="ui-btn-outline relative z-10 gap-2 px-4 py-2 text-sm" type="button" @click="openQuickModal">
            <AppIcon name="plus" class="h-4 w-4" aria-hidden="true" />
            {{ t("stepCategories.addCategory") }}
          </button>
        </div>
      </li>

      <li
        v-for="(cat, index) in filteredCategories"
        :key="cat.local_id"
      >
        <article
          class="ui-surface-lift ui-reveal group flex items-center gap-2.5 rounded-xl border border-slate-800 bg-slate-950/70 p-2 sm:gap-3 sm:p-2.5"
          :class="cat.is_published ? '' : 'opacity-70'"
          :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms`, 'content-visibility': 'auto', 'contain-intrinsic-size': 'auto 60px' }"
        >
          <!-- Reorder: stacked chevrons -->
          <div class="flex shrink-0 flex-col">
            <button
              class="ui-press ui-touch-target flex items-center justify-center rounded text-slate-500 transition hover:text-white disabled:opacity-20"
              type="button" :disabled="!canMoveCategoryUp(cat.local_id)" :aria-label="t('common.moveUp')"
              @click="moveCategory(cat.local_id, -1)"
            >
              <AppIcon name="chevronUp" class="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              class="ui-press ui-touch-target flex items-center justify-center rounded text-slate-500 transition hover:text-white disabled:opacity-20"
              type="button" :disabled="!canMoveCategoryDown(cat.local_id)" :aria-label="t('common.moveDown')"
              @click="moveCategory(cat.local_id, 1)"
            >
              <AppIcon name="chevronDown" class="h-4 w-4" aria-hidden="true" />
            </button>
          </div>

          <!-- Name + meta — in standalone mode navigates to dishes, otherwise opens editor -->
          <div
            role="button"
            tabindex="0"
            class="group/card min-w-0 flex-1 cursor-pointer text-start"
            :aria-label="props.standalone && cat.id
              ? `${t('stepCategories.viewDishes')} — ${cat.name || t('stepCategories.categoryNamePlaceholder')}`
              : `${t('common.edit')} ${cat.name || t('stepCategories.categoryNamePlaceholder')}`"
            @click="goToDishes(cat)"
            @keydown.enter.space.prevent="goToDishes(cat)"
          >
            <div class="flex items-center gap-1.5">
              <span class="h-1.5 w-1.5 shrink-0 rounded-full" aria-hidden="true" :class="cat.is_published ? 'bg-emerald-400' : 'bg-slate-600'" />
              <h3 class="truncate text-sm font-semibold text-white">{{ cat.name || t("stepCategories.categoryNamePlaceholder") }}</h3>
              <!-- Navigation hint: only shown in standalone mode when the category is saved -->
              <AppIcon
                v-if="props.standalone && cat.id"
                name="chevronRight"
                class="ms-auto h-3.5 w-3.5 shrink-0 text-slate-600 transition group-hover/card:translate-x-0.5 group-hover/card:text-slate-400"
                aria-hidden="true"
              />
            </div>
            <div class="mt-0.5 flex items-center gap-1.5 truncate text-xs text-slate-500">
              <span>{{ cat.is_published ? t("stepPublish.published") : t("stepPublish.draft") }}</span>
              <span v-if="Object.keys(cat.name_i18n || {}).length">· {{ Object.keys(cat.name_i18n || {}).length }} {{ t("stepCategories.translationsTitle") }}</span>
              <span v-if="cat.is_temporarily_disabled" class="inline-flex items-center gap-0.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-300">
                {{ t("stepCategories.pausedBadge") }}
              </span>
            </div>
            <p v-if="cat.is_temporarily_disabled" class="mt-0.5 text-[10px] text-amber-400/70">{{ t("stepCategories.pausedHint") }}</p>
          </div>

          <!-- Actions: pause/resume · edit · delete -->
          <div class="flex shrink-0 items-center gap-1.5">
            <button
              v-if="cat.id"
              class="ui-press ui-touch-target flex items-center justify-center rounded-lg border px-1.5 text-[10px] font-medium transition"
              :class="cat.is_temporarily_disabled
                ? 'border-amber-500/40 text-amber-300 hover:border-amber-400/60 hover:text-amber-200'
                : 'border-slate-700 text-slate-400 hover:border-slate-500 hover:text-slate-200'"
              type="button"
              :aria-label="cat.is_temporarily_disabled ? t('stepCategories.resumeToggle') : t('stepCategories.pauseToggle')"
              :disabled="pausingCatId === cat.id"
              @click="togglePause(cat)"
            >
              {{ cat.is_temporarily_disabled ? t("stepCategories.resumeToggle") : t("stepCategories.pauseToggle") }}
            </button>
            <button
              class="ui-press ui-touch-target flex items-center justify-center rounded-lg border border-slate-700 text-slate-300 transition hover:border-slate-500 hover:text-white"
              type="button" :aria-label="t('common.edit')" @click="openEditor(cat.local_id)"
            >
              <AppIcon name="pencil" class="h-3.5 w-3.5" aria-hidden="true" />
            </button>
            <button
              class="ui-press ui-touch-target flex items-center justify-center rounded-lg border border-red-400/25 text-red-300 transition hover:border-red-400/50 hover:text-red-200"
              type="button" :aria-label="t('common.remove')" @click="removeByLocalId(cat.local_id)"
            >
              <AppIcon name="trash" class="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        </article>
      </li>
    </ul>

    <Teleport to="body">
      <div
        v-if="editorOpen && editingCategory"
        class="fixed inset-0 z-[2100] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
        @click.self="closeEditor"
        @keydown.esc="closeEditor"
      >
        <div ref="editorDialogRef" role="dialog" aria-modal="true" aria-labelledby="step-categories-editor-dialog-title" class="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4 sm:px-5">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("common.categories") }}</p>
              <h3 id="step-categories-editor-dialog-title" class="text-lg font-semibold text-white">{{ t("stepCategories.editCategory") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline ui-touch-target px-3 py-1.5 text-xs" @click="closeEditor">{{ t("common.close") }}</button>
          </div>

          <div class="space-y-4 px-4 pt-4 pb-5 sm:px-5 sm:pt-5">
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
                      :aria-pressed="fieldLocales.name === locale.code"
                      class="ui-state-chip"
                      :data-active="fieldLocales.name === locale.code ? 'true' : undefined"
                      @click="fieldLocales.name = locale.code"
                    >
                      {{ locale.nativeLabel }}
                    </button>
                  </div>
                </div>
                <input
                  type="text"
                  :value="localizedFieldValue(editingCategory, 'name', fieldLocales.name)"
                  class="ui-input"
                  :placeholder="t('stepCategories.categoryNamePlaceholder')"
                  :aria-invalid="rowError(editingCategory, 'name') ? 'true' : undefined"
                  :aria-describedby="`step-cat-name-error-${editingCategory.local_id}`"
                  :aria-label="t('stepCategories.categoryNamePlaceholder')"
                  @input="setLocalizedFieldValue(editingCategory, 'name', fieldLocales.name, $event.target.value)"
                />
                <p v-if="rowError(editingCategory, 'name')" :id="`step-cat-name-error-${editingCategory.local_id}`" role="alert" class="text-xs text-red-300">{{ rowError(editingCategory, 'name') }}</p>
              </div>

              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepCategories.categoryDescriptionPlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`cat-desc-${locale.code}`"
                      type="button"
                      :aria-pressed="fieldLocales.description === locale.code"
                      class="ui-state-chip"
                      :data-active="fieldLocales.description === locale.code ? 'true' : undefined"
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
                  :aria-label="t('common.description')"
                  :placeholder="t('stepCategories.categoryDescriptionPlaceholder')"
                  @input="setLocalizedFieldValue(editingCategory, 'description', fieldLocales.description, $event.target.value)"
                ></textarea>
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <label class="space-y-1 text-sm text-slate-300">
                  <span class="text-xs text-slate-400">{{ t("stepSuperCategories.position") }}</span>
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
              <!-- Course sequencing -->
              <label class="space-y-1 text-sm text-slate-300">
                <span class="text-xs text-slate-400">{{ t("stepCategories.courseLabel") }}</span>
                <select v-model.number="editingCategory.course" class="ui-input">
                  <option :value="0">{{ t("stepCategories.courseNone") }}</option>
                  <option :value="1">{{ t("stepCategories.courseN", { n: 1 }) }}</option>
                  <option :value="2">{{ t("stepCategories.courseN", { n: 2 }) }}</option>
                  <option :value="3">{{ t("stepCategories.courseN", { n: 3 }) }}</option>
                  <option :value="4">{{ t("stepCategories.courseN", { n: 4 }) }}</option>
                </select>
                <p class="text-[11px] text-slate-500">{{ t("stepCategories.courseHint") }}</p>
              </label>
            </div>
          </div>

          <div class="sticky bottom-0 z-10 flex justify-end border-t border-slate-800 bg-slate-950/95 px-4 py-4 sm:px-5">
            <button type="button" class="ui-btn-primary px-4 py-2 text-sm" @click="closeEditor">{{ t("common.done") }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="quickModalOpen"
        class="fixed inset-0 z-[2100] flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm"
        @click.self="closeQuickModal"
        @keydown.esc="closeQuickModal"
      >
        <div ref="quickDialogRef" role="dialog" aria-modal="true" aria-labelledby="step-categories-quick-dialog-title" class="w-full max-w-2xl rounded-2xl border border-slate-700 bg-slate-950 shadow-2xl">
          <div class="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-800 bg-slate-950/95 px-4 py-4">
            <div class="space-y-1">
              <p class="ui-kicker">{{ t("common.categories") }}</p>
              <h3 id="step-categories-quick-dialog-title" class="text-lg font-semibold text-white">{{ t("stepCategories.addCategory") }}</h3>
            </div>
            <button type="button" class="ui-btn-outline ui-touch-target px-3 py-1.5 text-xs" @click="closeQuickModal">{{ t("common.close") }}</button>
          </div>
          <div class="space-y-4 p-4">
            <div class="rounded-2xl border border-slate-800 bg-slate-900/45 p-4 space-y-3">
              <label class="space-y-1 text-sm text-slate-300">
                <span class="text-xs text-slate-400">{{ t("stepCategories.selectSuperCategory") }}</span>
                <select v-model="quickCategory.super_category" class="ui-input" :class="quickAddErrors.superCategory ? 'border-red-400' : ''" :aria-invalid="quickAddErrors.superCategory ? 'true' : undefined" aria-describedby="step-cat-quick-supcat-error" @change="quickAddErrors.superCategory = ''">
                  <option v-for="group in sortedSuperCategoryOptions" :key="group.id" :value="Number(group.id)">{{ superCategoryLabel(group) }}</option>
                </select>
                <p v-if="quickAddErrors.superCategory" id="step-cat-quick-supcat-error" role="alert" class="text-xs text-red-300 mt-1">{{ quickAddErrors.superCategory }}</p>
              </label>

              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepCategories.categoryNamePlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`quick-cat-name-${locale.code}`"
                      type="button"
                      :aria-pressed="quickFieldLocales.name === locale.code"
                      class="ui-state-chip"
                      :data-active="quickFieldLocales.name === locale.code ? 'true' : undefined"
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
                  :class="quickAddErrors.name ? 'border-red-400' : ''"
                  :placeholder="t('stepCategories.categoryNamePlaceholder')"
                  :aria-label="t('stepCategories.categoryNamePlaceholder')"
                  :aria-invalid="quickAddErrors.name ? 'true' : undefined"
                  aria-describedby="step-cat-quick-name-error"
                  @input="setLocalizedQuickFieldValue('name', quickFieldLocales.name, $event.target.value); quickAddErrors.name = ''"
                />
                <p v-if="quickAddErrors.name" id="step-cat-quick-name-error" role="alert" class="text-xs text-red-300 mt-1">{{ quickAddErrors.name }}</p>
              </div>

              <div class="space-y-1">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <p class="text-xs text-slate-400">{{ t("stepCategories.categoryDescriptionPlaceholder") }}</p>
                  <div class="flex flex-wrap gap-1">
                    <button
                      v-for="locale in availableContentLocales"
                      :key="`quick-cat-desc-${locale.code}`"
                      type="button"
                      :aria-pressed="quickFieldLocales.description === locale.code"
                      class="ui-state-chip"
                      :data-active="quickFieldLocales.description === locale.code ? 'true' : undefined"
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
                  :aria-label="t('common.description')"
                  :placeholder="t('stepCategories.categoryDescriptionPlaceholder')"
                  @input="setLocalizedQuickFieldValue('description', quickFieldLocales.description, $event.target.value)"
                ></textarea>
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <input v-model.number="quickCategory.position" type="number" min="0" class="ui-input" :aria-label="t('stepSuperCategories.position')" :placeholder="t('stepSuperCategories.position')" />
                <select v-model="quickCategory.is_published" :aria-label="t('stepCategories.visibility')" class="ui-input">
                  <option :value="true">{{ t("common.available") }}</option>
                  <option :value="false">{{ t("common.soon") }}</option>
                </select>
              </div>
              <!-- Course sequencing -->
              <label class="space-y-1 text-sm text-slate-300">
                <span class="text-xs text-slate-400">{{ t("stepCategories.courseLabel") }}</span>
                <select v-model.number="quickCategory.course" class="ui-input">
                  <option :value="0">{{ t("stepCategories.courseNone") }}</option>
                  <option :value="1">{{ t("stepCategories.courseN", { n: 1 }) }}</option>
                  <option :value="2">{{ t("stepCategories.courseN", { n: 2 }) }}</option>
                  <option :value="3">{{ t("stepCategories.courseN", { n: 3 }) }}</option>
                  <option :value="4">{{ t("stepCategories.courseN", { n: 4 }) }}</option>
                </select>
                <p class="text-[11px] text-slate-500">{{ t("stepCategories.courseHint") }}</p>
              </label>
            </div>
          </div>
          <div class="sticky bottom-0 z-10 flex justify-end gap-2 border-t border-slate-800 bg-slate-950/95 px-4 py-4">
            <button type="button" class="ui-btn-outline px-4 py-2 text-sm" @click="closeQuickModal">{{ t("common.close") }}</button>
            <button type="button" class="ui-btn-primary gap-2 px-4 py-2 text-sm" @click="quickAdd">
              <AppIcon name="plus" class="h-4 w-4" aria-hidden="true" />
              {{ t("stepCategories.addCategory") }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <div v-if="globalError" class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5" role="alert">
      <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
      <p class="flex-1 text-sm text-red-300">{{ globalError }}</p>
    </div>

    <div class="flex flex-wrap items-center gap-3 border-t border-slate-800/80 pt-3">
      <button type="button" class="ui-btn-primary gap-2 px-4 py-2" :disabled="saving || !superCategoryOptions.length" @click="saveAll">
        <AppIcon :name="saving ? 'refresh' : 'check'" class="h-4 w-4" aria-hidden="true" />
        {{ saving ? t("common.saving") : props.standalone ? t("common.save") : t("common.saveAndNext") }}
      </button>
      <button v-if="!props.standalone" type="button" class="ui-btn-outline px-4 py-2" @click="$emit('back')">{{ t("common.previous") }}</button>
      <p class="text-sm text-slate-400" role="status" aria-live="polite">{{ status }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import api from "../lib/api";
import { categoryApi, superCategoryApi } from "../lib/onboardingApi";
import { useI18n } from "../composables/useI18n";
import { useConfirmModal } from "../composables/useConfirmModal";
import { useFocusTrap } from "../composables/useFocusTrap";
import { LOCALE_OPTIONS, normalizeLocale } from "../i18n/config";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

const props = defineProps({ standalone: { type: Boolean, default: false } });
const emit = defineEmits(["next", "back"]);
const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const tenant = useTenantStore();
const toast = useToastStore();
const { confirm } = useConfirmModal();

const categories = reactive([]);
const removedIds = ref([]);
const rowErrors = reactive({});
const globalError = ref("");
const saving = ref(false);
const pausingCatId = ref(null);
const status = ref("");
const search = ref("");
const superCategoryOptions = ref([]);
const activeSuperCategoryId = ref("");
const editorDialogRef = ref(null);
const quickDialogRef  = ref(null);
const editorOpen = ref(false);
const editorLocalId = ref("");
const fieldLocales = reactive({ name: "en", description: "en" });
const quickFieldLocales = reactive({ name: "en", description: "en" });
const quickModalOpen = ref(false);
const quickNameInputRef = ref(null);

useFocusTrap(editorDialogRef, editorOpen);
useFocusTrap(quickDialogRef, quickModalOpen);
const quickAddErrors = reactive({ name: "", superCategory: "" });
const quickCategory = reactive({
  local_id: "quick-category",
  super_category: "",
  name: "",
  name_i18n: {},
  description: "",
  description_i18n: {},
  position: 0,
  is_published: true,
  course: 0,
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
  const source = [...activeCategories.value].sort((a, b) => (Number(a.position || 0) - Number(b.position || 0)) || String(a.name || "").localeCompare(String(b.name || "")));
  if (!query) return source;
  return source.filter((cat) => [cat.name, cat.description, cat.slug].filter(Boolean).some((value) => String(value).toLowerCase().includes(query)));
});
const editingCategory = computed(() => categories.find((cat) => String(cat.local_id) === String(editorLocalId.value)) || null);
const orderedActiveCategories = computed(() => [...activeCategories.value].sort((a, b) => (Number(a.position || 0) - Number(b.position || 0)) || String(a.name || "").localeCompare(String(b.name || ""))));

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
  is_temporarily_disabled: cat.is_temporarily_disabled ?? false,
  course: Number(cat.course) || 0,
  dish_count: typeof cat.dish_count === "number" ? cat.dish_count : 0,
});

const superCategoryLabel = (group) => {
  if (!group) return "";
  const status = group.is_temporarily_disabled ? t("stepSuperCategories.disabled") : null;
  return status ? `${group.name} · ${status}` : String(group.name || "");
};

let superQueryConsumed = false;
const syncActiveSuperCategory = () => {
  if (!sortedSuperCategoryOptions.value.length) {
    activeSuperCategoryId.value = "";
    return;
  }
  // Honor a ?super=<id> deep-link once (drill-in from the super-category list),
  // then leave the dropdown under the user's control.
  if (!superQueryConsumed) {
    const requested = route.query.super ? String(route.query.super) : "";
    if (requested && sortedSuperCategoryOptions.value.some((group) => String(group.id) === requested)) {
      activeSuperCategoryId.value = requested;
      superQueryConsumed = true;
      return;
    }
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

const renumberCategoriesForGroup = (groupId) => {
  const ordered = categories
    .filter((cat) => String(cat.super_category) === String(groupId))
    .sort((a, b) => (Number(a.position || 0) - Number(b.position || 0)) || String(a.name || "").localeCompare(String(b.name || "")));
  ordered.forEach((cat, index) => {
    cat.position = index;
  });
};

const canMoveCategoryUp = (localId) => orderedActiveCategories.value.findIndex((cat) => String(cat.local_id) === String(localId)) > 0;
const canMoveCategoryDown = (localId) => {
  const index = orderedActiveCategories.value.findIndex((cat) => String(cat.local_id) === String(localId));
  return index > -1 && index < orderedActiveCategories.value.length - 1;
};

const moveCategory = (localId, direction) => {
  const ordered = [...orderedActiveCategories.value];
  const index = ordered.findIndex((cat) => String(cat.local_id) === String(localId));
  const targetIndex = index + direction;
  if (index < 0 || targetIndex < 0 || targetIndex >= ordered.length) return;
  [ordered[index], ordered[targetIndex]] = [ordered[targetIndex], ordered[index]];
  ordered.forEach((cat, orderedIndex) => {
    cat.position = orderedIndex;
  });
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

// In the standalone menu-builder context, clicking the card body navigates to
// the Dishes tab pre-filtered to this category instead of opening the editor.
// The pen (pencil) button still opens the editor.
const goToDishes = (cat) => {
  if (props.standalone && cat.id) {
    router.replace({ name: "owner-menu-builder", query: { ...route.query, tab: "dishes", category: String(cat.id) } });
  } else {
    openEditor(cat.local_id);
  }
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
  quickCategory.course = 0;
  quickFieldLocales.name = defaultLocale.value;
  quickFieldLocales.description = defaultLocale.value;
  quickAddErrors.name = "";
  quickAddErrors.superCategory = "";
  quickModalOpen.value = true;
  nextTick(() => quickNameInputRef.value?.focus());
};
const closeQuickModal = () => {
  quickModalOpen.value = false;
};

const quickAdd = () => {
  quickAddErrors.name = "";
  quickAddErrors.superCategory = "";
  const name = String(quickCategory.name || "").trim();
  if (!quickCategory.super_category) {
    quickAddErrors.superCategory = t("stepCategories.superCategoryRequired");
    return;
  }
  if (name.length < 2) {
    quickAddErrors.name = t("stepCategories.nameMin");
    return;
  }
  const allowedTranslationLocales = availableContentLocales.value.map((locale) => locale.code).filter((locale) => locale !== defaultLocale.value);
  categories.push(normalizeCategory({
    super_category: quickCategory.super_category,
    name,
    name_i18n: pickI18nMap(quickCategory.name_i18n, allowedTranslationLocales),
    description: String(quickCategory.description || "").trim(),
    description_i18n: pickI18nMap(quickCategory.description_i18n, allowedTranslationLocales),
    position: orderedActiveCategories.value.length,
    is_published: quickCategory.is_published,
    course: Number(quickCategory.course) || 0,
  }));
  activeSuperCategoryId.value = String(quickCategory.super_category);
  renumberCategoriesForGroup(quickCategory.super_category);
  closeQuickModal();
};

const removeByLocalId = async (localId) => {
  const index = categories.findIndex((cat) => cat.local_id === localId);
  if (index < 0) return;
  const cat = categories[index];
  const catName = cat?.name?.trim() || t("stepCategories.cardLabel", { index: index + 1 });
  const dishCount = cat?.dish_count ?? 0;
  const body = dishCount > 0 ? t("stepCategories.removeConfirmDishCount", { count: dishCount }) : undefined;
  const ok = await confirm({
    title: t("stepCategories.removeConfirm", { name: catName }),
    body,
    confirmLabel: t("common.remove"),
    danger: true,
  });
  if (!ok) return;
  categories.splice(index, 1);
  if (cat?.id) removedIds.value.push(cat.id);
  if (String(editorLocalId.value) === String(localId)) closeEditor();
  delete rowErrors[localId];
  renumberCategoriesForGroup(cat.super_category);
};

const togglePause = async (cat) => {
  if (!cat.id || pausingCatId.value === cat.id) return;
  const next = !cat.is_temporarily_disabled;
  // Optimistic update
  cat.is_temporarily_disabled = next;
  pausingCatId.value = cat.id;
  try {
    await api.patch(`/categories/${cat.id}/`, { is_temporarily_disabled: next });
  } catch {
    // Revert on failure
    cat.is_temporarily_disabled = !next;
    toast.show(t("stepCategories.pauseFailed"), "error");
  } finally {
    pausingCatId.value = null;
  }
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

const onModalEscape = (e) => {
  if (e.key !== "Escape") return;
  if (quickModalOpen.value) closeQuickModal();
  else if (editorOpen.value) closeEditor();
};
onMounted(() => document.addEventListener("keydown", onModalEscape));
onUnmounted(() => document.removeEventListener("keydown", onModalEscape));

onMounted(load);
</script>
