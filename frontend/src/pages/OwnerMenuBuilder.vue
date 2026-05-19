<template>
  <div class="space-y-4">
    <section class="ui-panel overflow-hidden p-4 sm:p-5">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-2">
          <p class="ui-section-kicker">{{ t("ownerLayout.menuBuilder") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white sm:text-3xl">{{ activeTabTitle }}</h2>
        </div>
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
          <!-- CSV import button -->
          <button
            class="inline-flex items-center gap-1.5 rounded-xl border border-indigo-500/40 bg-indigo-500/10 px-3 py-2 text-xs font-semibold text-indigo-300 hover:border-indigo-400/60 hover:bg-indigo-500/15 transition-colors"
            @click="showImport = true"
          >
            <AppIcon name="upload" class="h-3.5 w-3.5" />
            {{ t("ownerMenuBuilder.importCsv") }}
          </button>
          <nav class="owner-menu-builder-nav" aria-label="Menu builder sections">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              type="button"
              class="owner-menu-builder-nav-item"
              :data-active="activeTab === tab.key"
              @click="setTab(tab.key)"
            >
              <AppIcon :name="tab.icon" class="owner-menu-builder-nav-icon" />
              <span>{{ tab.label }}</span>
            </button>
          </nav>
        </div>
      </div>
    </section>

    <component :is="activeComponent" standalone />

    <!-- CSV Import Modal -->
    <Teleport to="body">
      <div
        v-if="showImport"
        class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm px-4 pb-4 sm:pb-0"
        @click.self="closeImport"
      >
        <div class="w-full max-w-lg bg-slate-900 rounded-2xl border border-slate-700 p-6 space-y-4 max-h-[90vh] overflow-y-auto">
          <!-- Header -->
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-base font-bold text-white">{{ t("ownerMenuBuilder.importTitle") }}</h2>
              <p class="text-xs text-slate-400 mt-0.5">{{ t("ownerMenuBuilder.importSubtitle") }}</p>
            </div>
            <button class="text-slate-400 hover:text-white text-xl leading-none" @click="closeImport">✕</button>
          </div>

          <!-- Format guide + template download -->
          <div class="rounded-xl border border-slate-700/60 bg-slate-800/40 p-3 space-y-2">
            <p class="text-xs font-semibold text-slate-300">{{ t("ownerMenuBuilder.importFormatTitle") }}</p>
            <p class="text-[11px] text-slate-400 font-mono">category_name, dish_name, description, price, tags, allergens</p>
            <ul class="text-[11px] text-slate-500 space-y-0.5 list-disc list-inside">
              <li>{{ t("ownerMenuBuilder.importHint1") }}</li>
              <li>{{ t("ownerMenuBuilder.importHint2") }}</li>
              <li>{{ t("ownerMenuBuilder.importHint3") }}</li>
            </ul>
            <a
              :href="templateUrl"
              class="inline-flex items-center gap-1.5 text-[11px] text-indigo-300 hover:text-indigo-200 transition-colors"
            >
              <AppIcon name="download" class="h-3 w-3" />
              {{ t("ownerMenuBuilder.downloadTemplate") }}
            </a>
          </div>

          <!-- File picker -->
          <div v-if="!importResult">
            <label class="block space-y-2">
              <span class="text-xs font-medium text-slate-400">{{ t("ownerMenuBuilder.importChooseFile") }}</span>
              <div
                class="flex items-center justify-center rounded-xl border-2 border-dashed border-slate-600 bg-slate-900/40 px-4 py-6 cursor-pointer hover:border-indigo-500/50 transition-colors"
                @dragover.prevent
                @drop.prevent="onFileDrop"
                @click="fileInputRef?.click()"
              >
                <div class="text-center space-y-1">
                  <AppIcon name="upload" class="h-6 w-6 mx-auto text-slate-500" />
                  <p v-if="selectedFile" class="text-xs font-semibold text-indigo-300">{{ selectedFile.name }}</p>
                  <p v-else class="text-xs text-slate-400">{{ t("ownerMenuBuilder.importDragDrop") }}</p>
                </div>
              </div>
              <input
                ref="fileInputRef"
                type="file"
                accept=".csv,text/csv"
                class="sr-only"
                @change="onFileChange"
              />
            </label>

            <p v-if="importError" class="mt-2 text-xs text-red-300">{{ importError }}</p>

            <button
              class="ui-btn-primary mt-4 w-full justify-center"
              :disabled="!selectedFile || importing"
              @click="runImport"
            >
              {{ importing ? t("ownerMenuBuilder.importing") : t("ownerMenuBuilder.importStart") }}
            </button>
          </div>

          <!-- Results -->
          <div v-else class="space-y-3">
            <div class="grid grid-cols-3 gap-2">
              <div class="rounded-xl border border-emerald-500/30 bg-emerald-500/8 p-3 text-center">
                <p class="text-xl font-bold text-emerald-300">{{ importResult.created_dishes }}</p>
                <p class="text-[10px] text-emerald-400/70 mt-0.5">{{ t("ownerMenuBuilder.resultDishes") }}</p>
              </div>
              <div class="rounded-xl border border-indigo-500/30 bg-indigo-500/8 p-3 text-center">
                <p class="text-xl font-bold text-indigo-300">{{ importResult.created_categories }}</p>
                <p class="text-[10px] text-indigo-400/70 mt-0.5">{{ t("ownerMenuBuilder.resultCategories") }}</p>
              </div>
              <div class="rounded-xl border border-slate-700/60 bg-slate-800/40 p-3 text-center">
                <p class="text-xl font-bold text-slate-300">{{ importResult.skipped }}</p>
                <p class="text-[10px] text-slate-400/70 mt-0.5">{{ t("ownerMenuBuilder.resultSkipped") }}</p>
              </div>
            </div>

            <div v-if="importResult.errors?.length" class="rounded-xl border border-amber-500/30 bg-amber-500/8 p-3 space-y-1">
              <p class="text-xs font-semibold text-amber-300">{{ t("ownerMenuBuilder.resultWarnings") }}</p>
              <p v-for="(err, i) in importResult.errors" :key="i" class="text-[11px] text-amber-200/70">• {{ err }}</p>
            </div>

            <div class="flex gap-2">
              <button class="flex-1 rounded-xl border border-slate-700 py-2 text-sm text-slate-300 hover:border-slate-500 transition-colors" @click="resetImport">
                {{ t("ownerMenuBuilder.importAgain") }}
              </button>
              <button class="ui-btn-primary flex-1 justify-center" @click="closeImport">
                {{ t("common.close") }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import api from "../lib/api";
import StepSuperCategories from "../onboarding/StepSuperCategories.vue";
import StepCategories from "../onboarding/StepCategories.vue";
import StepDishes from "../onboarding/StepDishes.vue";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const toast = useToastStore();

// ── Tabs ──────────────────────────────────────────────────────────────────────
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
    label: t("onboardingWizard.steps.categories.title"),
    description: t("onboardingWizard.steps.categories.description"),
    icon: "menu",
    component: StepCategories,
  },
  {
    key: "dishes",
    label: t("onboardingWizard.steps.dishes.title"),
    description: t("onboardingWizard.steps.dishes.description"),
    icon: "cart",
    component: StepDishes,
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

const setTab = (tab) => {
  if (tab === activeTab.value) return;
  router.replace({ name: "owner-menu-builder", query: { ...route.query, tab } });
};

// ── CSV Import ────────────────────────────────────────────────────────────────
const showImport = ref(false);
const fileInputRef = ref(null);
const selectedFile = ref(null);
const importing = ref(false);
const importError = ref('');
const importResult = ref(null);

const templateUrl = computed(() => {
  const base = api.defaults?.baseURL || '';
  return `${base}/api/owner/menu/import/`;
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

<style scoped>
.owner-menu-builder-nav {
  display: inline-grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.5rem;
  width: 100%;
  max-width: 32rem;
  border: 1px solid rgba(51, 65, 85, 0.72);
  border-radius: 1rem;
  background: linear-gradient(135deg, rgba(2, 6, 23, 0.86), rgba(3, 15, 35, 0.78));
  padding: 0.35rem;
}

.owner-menu-builder-nav-item {
  min-height: 2.85rem;
  border-radius: 0.8rem;
  border: 1px solid rgba(51, 65, 85, 0.4);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.6rem 0.8rem;
  color: rgb(203, 213, 225);
  font-size: 0.86rem;
  font-weight: 600;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.owner-menu-builder-nav-item:hover {
  border-color: rgba(245, 158, 11, 0.55);
  background: rgba(15, 23, 42, 0.72);
  color: rgb(245, 158, 11);
}

.owner-menu-builder-nav-item[data-active="true"] {
  border-color: rgba(245, 158, 11, 0.82);
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.08));
  color: rgb(245, 158, 11);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.12) inset;
}

.owner-menu-builder-nav-icon {
  width: 0.9rem;
  height: 0.9rem;
  flex-shrink: 0;
}

@media (max-width: 640px) {
  .owner-menu-builder-nav {
    display: flex;
    max-width: none;
    overflow-x: auto;
    padding: 0.3rem;
    scrollbar-width: none;
  }

  .owner-menu-builder-nav::-webkit-scrollbar {
    display: none;
  }

  .owner-menu-builder-nav-item {
    min-height: 2.45rem;
    flex: 0 0 auto;
    font-size: 0.76rem;
    padding: 0.48rem 0.72rem;
  }

  .owner-menu-builder-nav-icon {
    width: 0.8rem;
    height: 0.8rem;
  }
}
</style>
