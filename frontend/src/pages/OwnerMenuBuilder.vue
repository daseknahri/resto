<template>
  <div class="space-y-3">
    <!-- Compact toolbar — the active tab pill already indicates the section, so the heavy
         title panel is dropped to reclaim working room. -->
    <div class="ui-toolbar-band space-y-2.5">
      <div class="flex items-center justify-between gap-3">
        <h2 class="ui-display min-w-0 truncate text-base font-semibold text-white sm:text-lg">{{ activeTabTitle }}</h2>
        <div class="flex shrink-0 items-center gap-2">
          <button
            class="ui-btn-outline ui-press gap-1.5 px-3 py-1.5 text-xs"
            @click="showTemplates = true"
          >
            <AppIcon name="sparkles" class="h-3.5 w-3.5" aria-hidden="true" />
            <span class="hidden sm:inline">{{ t("ownerTemplates.button") }}</span>
            <span class="sr-only sm:hidden">{{ t("ownerTemplates.button") }}</span>
          </button>
          <button
            class="ui-btn-outline ui-press gap-1.5 px-3 py-1.5 text-xs"
            @click="showImport = true"
          >
            <AppIcon name="upload" class="h-3.5 w-3.5" aria-hidden="true" />
            <span class="hidden sm:inline">{{ t("ownerMenuBuilder.importCsv") }}</span>
            <span class="sr-only sm:hidden">{{ t("ownerMenuBuilder.importCsv") }}</span>
          </button>
        </div>
      </div>
      <nav class="ui-segmented" role="tablist" :aria-label="t('common.sectionsNav')">
        <button
          v-for="tab in tabs"
          :id="'owner-mb-tab-' + tab.key"
          :key="tab.key"
          type="button"
          class="ui-segmented-button flex-1"
          :data-active="activeTab === tab.key"
          role="tab"
          :aria-selected="activeTab === tab.key"
          :aria-controls="'owner-mb-panel-' + tab.key"
          @click="setTab(tab.key)"
        >
          <AppIcon :name="tab.icon" class="me-1.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{{ tab.label }}</span>
        </button>
      </nav>
    </div>

    <div
      :id="'owner-mb-panel-' + activeTab"
      ref="mbPanelRef"
      role="tabpanel"
      tabindex="-1"
      :aria-labelledby="'owner-mb-tab-' + activeTab"
      class="focus-visible:outline-none"
    >
      <component :is="activeComponent" :key="reloadKey" standalone />
    </div>

    <!-- CSV Import Modal -->
    <Teleport to="body">
      <Transition name="ui-fade">
        <div
          v-if="showImport"
          class="fixed inset-0 z-[2100] flex items-end justify-center bg-black/60 px-4 pb-4 backdrop-blur-sm sm:items-center sm:pb-0"
          @click.self="closeImport"
          @keydown.esc="closeImport"
        >
          <div
            ref="importDialogRef"
            role="dialog"
            aria-modal="true"
            aria-labelledby="owner-menu-builder-import-dialog-title"
            class="ui-panel w-full max-w-lg max-h-[90vh] overflow-y-auto space-y-4 p-5 sm:p-6"
          >
            <!-- Header -->
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="ui-kicker">{{ t("ownerMenuBuilder.importCsv") }}</p>
                <h2 id="owner-menu-builder-import-dialog-title" class="text-base font-bold text-white leading-tight mt-0.5">{{ t("ownerMenuBuilder.importTitle") }}</h2>
                <p class="ui-subtle mt-0.5 text-xs">{{ t("ownerMenuBuilder.importSubtitle") }}</p>
              </div>
              <button
                ref="importCloseBtnRef"
                class="ui-press ui-touch-target shrink-0 flex items-center justify-center rounded-xl border border-slate-700/60 bg-slate-800/50 text-slate-400 transition hover:border-slate-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                :aria-label="t('common.close')"
                @click="closeImport"
              >
                <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <!-- Format guide + template download -->
            <div class="ui-section-band space-y-2 p-3">
              <p class="text-xs font-semibold text-slate-300">{{ t("ownerMenuBuilder.importFormatTitle") }}</p>
              <p class="text-[11px] font-mono text-slate-400 break-all">category_name, dish_name, description, price, tags, allergens</p>
              <ul class="space-y-0.5 text-[11px] text-slate-500 list-disc list-inside">
                <li>{{ t("ownerMenuBuilder.importHint1") }}</li>
                <li>{{ t("ownerMenuBuilder.importHint2") }}</li>
                <li>{{ t("ownerMenuBuilder.importHint3") }}</li>
              </ul>
              <a
                :href="templateUrl"
                class="inline-flex items-center gap-1.5 text-[11px] text-[var(--color-secondary)] transition hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60 rounded"
              >
                <AppIcon name="download" class="h-3 w-3 shrink-0" aria-hidden="true" />
                {{ t("ownerMenuBuilder.downloadTemplate") }}
              </a>
            </div>

            <!-- File picker -->
            <div v-if="!importResult" class="space-y-3">
              <label class="block space-y-2">
                <span class="text-xs font-medium text-slate-400">{{ t("ownerMenuBuilder.importChooseFile") }}</span>
                <div
                  tabindex="-1"
                  class="flex items-center justify-center rounded-xl border-2 border-dashed border-slate-700/70 bg-slate-950/40 px-4 py-8 cursor-pointer transition hover:border-[var(--color-secondary)]/50 hover:bg-slate-950/60 focus-within:border-[var(--color-secondary)]/60"
                  @dragover.prevent
                  @drop.prevent="onFileDrop"
                  @click="fileInputRef?.click()"
                  @keydown.enter.prevent="fileInputRef?.click()"
                  @keydown.space.prevent="fileInputRef?.click()"
                >
                  <div class="text-center space-y-1.5">
                    <AppIcon name="upload" class="h-7 w-7 mx-auto text-slate-500" aria-hidden="true" />
                    <p v-if="selectedFile" class="text-xs font-semibold text-[var(--color-secondary)] break-all px-2">{{ selectedFile.name }}</p>
                    <p v-else class="text-xs text-slate-400">{{ t("ownerMenuBuilder.importDragDrop") }}</p>
                  </div>
                </div>
                <input
                  ref="fileInputRef"
                  type="file"
                  accept=".csv,text/csv"
                  class="sr-only"
                  :aria-invalid="importError ? 'true' : undefined"
                  :aria-describedby="importError ? 'owner-menu-builder-import-error' : undefined"
                  @change="onFileChange"
                />
              </label>

              <div
                v-if="importError"
                id="owner-menu-builder-import-error"
                class="flex items-start gap-2 rounded-xl border border-red-500/30 bg-red-500/8 px-3 py-2.5"
                role="alert"
              >
                <AppIcon name="info" class="mt-0.5 h-4 w-4 shrink-0 text-red-400" aria-hidden="true" />
                <p class="flex-1 text-xs text-red-300">{{ importError }}</p>
              </div>

              <button
                class="ui-btn-primary w-full justify-center"
                :disabled="!selectedFile || importing"
                :aria-busy="importing"
                @click="runImport"
              >
                <AppIcon v-if="importing" name="refresh" class="h-4 w-4 animate-spin me-1.5" aria-hidden="true" />
                {{ importing ? t("ownerMenuBuilder.importing") : t("ownerMenuBuilder.importStart") }}
              </button>
            </div>

            <!-- Results -->
            <div v-else class="space-y-3">
              <div class="grid grid-cols-3 gap-2">
                <div class="rounded-xl border border-emerald-500/30 bg-emerald-500/8 p-3 text-center space-y-0.5">
                  <p class="text-xl font-bold tabular-nums text-emerald-300">{{ importResult.created_dishes }}</p>
                  <p class="text-[11px] text-emerald-400 leading-tight">{{ t("ownerMenuBuilder.resultDishes") }}</p>
                </div>
                <div class="rounded-xl border border-indigo-500/30 bg-indigo-500/8 p-3 text-center space-y-0.5">
                  <p class="text-xl font-bold tabular-nums text-indigo-300">{{ importResult.created_categories }}</p>
                  <p class="text-[11px] text-indigo-400 leading-tight">{{ t("ownerMenuBuilder.resultCategories") }}</p>
                </div>
                <div class="rounded-xl border border-slate-700/60 bg-slate-800/40 p-3 text-center space-y-0.5">
                  <p class="text-xl font-bold tabular-nums text-slate-300">{{ importResult.skipped }}</p>
                  <p class="text-[11px] text-slate-400 leading-tight">{{ t("ownerMenuBuilder.resultSkipped") }}</p>
                </div>
              </div>

              <div
                v-if="importResult.errors?.length"
                class="rounded-xl border border-amber-500/30 bg-amber-500/8 p-3 space-y-1"
                role="alert"
              >
                <p class="text-xs font-semibold text-amber-300">{{ t("ownerMenuBuilder.resultWarnings") }}</p>
                <p v-for="(err, i) in importResult.errors" :key="i" class="text-[11px] text-amber-200">&#x2022; {{ err }}</p>
              </div>

              <div class="flex gap-2">
                <button class="ui-btn-outline ui-press flex-1" @click="resetImport">
                  {{ t("ownerMenuBuilder.importAgain") }}
                </button>
                <button class="ui-btn-primary flex-1 justify-center" @click="closeImport">
                  {{ t("common.close") }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Templates modal — start from a professionally themed sample menu -->
    <TemplatePickerModal :open="showTemplates" @close="showTemplates = false" @applied="onTemplateApplied" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import TemplatePickerModal from "../components/TemplatePickerModal.vue";
import { useI18n } from "../composables/useI18n";
import { useVocabulary } from "../composables/useVocabulary";
import { useToastStore } from "../stores/toast";
import api from "../lib/api";
import StepSuperCategories from "../onboarding/StepSuperCategories.vue";
import StepCategories from "../onboarding/StepCategories.vue";
import StepDishes from "../onboarding/StepDishes.vue";
import OwnerInventory from "../components/OwnerInventory.vue";

// Explicit name so <KeepAlive :exclude> in OwnerLayout reliably skips this page
// (editing surface — keep its data fresh and its cleanup running on unmount).
defineOptions({ name: "OwnerMenuBuilder" });

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const { itemPlural, groupPlural } = useVocabulary();
const toast = useToastStore();

// ── Starter templates ───────────────────────────────────────────────────────────
const showTemplates = ref(false);
// Bumped after applying a template to remount the active tab so new menu shows.
const reloadKey = ref(0);

// TemplatePickerModal (wrapping TemplateGallery) handles fetching, applying,
// tenant.fetchMeta(), and toasts internally — we only need to close the modal
// and bump reloadKey so the active tab remounts with the new menu data.
const onTemplateApplied = () => {
  showTemplates.value = false;
  reloadKey.value += 1;
};

// ── Tabs ──────────────────────────────────────────────────────────────────────
// Category/Dish tab labels flex by business_type (shops read "Sections"/"Products").
const tabs = computed(() => [
  {
    key: "super-categories",
    label: t("stepSuperCategories.heading"),
    description: t("stepSuperCategories.description"),
    icon: "filter",
    component: StepSuperCategories,
  },
  {
    key: "categories",
    label: groupPlural.value,
    description: t("onboardingWizard.steps.categories.description"),
    icon: "menu",
    component: StepCategories,
  },
  {
    key: "dishes",
    label: itemPlural.value,
    description: t("onboardingWizard.steps.dishes.description"),
    icon: "cart",
    component: StepDishes,
  },
  {
    key: "inventory",
    label: t("inventory.tab"),
    description: t("inventory.tab"),
    icon: "chart",
    component: OwnerInventory,
  },
]);

const validTabKeys = computed(() => tabs.value.map((tab) => tab.key));
const activeTab = computed(() => {
  const tab = String(route.query.tab || "super-categories").toLowerCase();
  return validTabKeys.value.includes(tab) ? tab : "super-categories";
});
const activeTabConfig = computed(() => tabs.value.find((tab) => tab.key === activeTab.value) || tabs.value[0]);
const activeComponent = computed(() => activeTabConfig.value.component);
const activeTabTitle = computed(() => activeTabConfig.value.label);

const mbPanelRef = ref(null);
// Move focus to the panel wrapper after each tab switch (WCAG 2.4.3).
watch(activeTab, () => { nextTick(() => mbPanelRef.value?.focus()); });

const setTab = (tab) => {
  if (tab === activeTab.value) return;
  router.replace({ name: "owner-menu-builder", query: { ...route.query, tab } });
};

// ── CSV Import ────────────────────────────────────────────────────────────────
const importDialogRef  = ref(null);
const importCloseBtnRef = ref(null);

// Focus trap for the import dialog
const FOCUSABLE = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const trapImportFocus = (e) => {
  if (!importDialogRef.value) return;
  const focusable = Array.from(importDialogRef.value.querySelectorAll(FOCUSABLE));
  if (!focusable.length || e.key !== 'Tab') return;
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
  }
};

const showImport = ref(false);
const fileInputRef = ref(null);
const selectedFile = ref(null);
const importing = ref(false);
const importError = ref('');
const importResult = ref(null);

// showImport must be declared above this watch: referencing it earlier hits the
// temporal dead zone ("Cannot access 'showImport' before initialization") and
// crashes setup() the moment the page loads.
let _importReturnFocus = null;
watch(showImport, async (open) => {
  if (open) {
    _importReturnFocus = document.activeElement;
    await nextTick();
    importCloseBtnRef.value?.focus();
    document.addEventListener('keydown', trapImportFocus);
  } else {
    document.removeEventListener('keydown', trapImportFocus);
    _importReturnFocus?.focus();
    _importReturnFocus = null;
  }
});
onBeforeUnmount(() => document.removeEventListener('keydown', trapImportFocus));

const templateUrl = computed(() => {
  // api.defaults.baseURL is already "/api" — don't prefix with it again.
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  return `${origin}/api/owner/menu/import/`;
});

const closeImport = () => {
  showImport.value = false;
  resetImport();
};

const resetImport = () => {
  selectedFile.value = null;
  importError.value = '';
  importResult.value = null;
  importing.value = false;
};

const onFileChange = (e) => {
  const file = e.target.files?.[0];
  if (file) {
    selectedFile.value = file;
    importError.value = '';
  }
};

const onFileDrop = (e) => {
  const file = e.dataTransfer?.files?.[0];
  if (file) {
    selectedFile.value = file;
    importError.value = '';
  }
};

const runImport = async () => {
  if (!selectedFile.value) return;
  importing.value = true;
  importError.value = '';
  try {
    const formData = new FormData();
    formData.append('file', selectedFile.value);
    const res = await api.post('/owner/menu/import/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    importResult.value = res.data;
    if (res.data.created_dishes > 0) {
      toast.show(t('ownerMenuBuilder.importSuccess', { count: res.data.created_dishes }), 'success');
    }
  } catch (err) {
    importError.value = err?.response?.data?.detail || t('ownerMenuBuilder.importFailed');
  } finally {
    importing.value = false;
  }
};
</script>
