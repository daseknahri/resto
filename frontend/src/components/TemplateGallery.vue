<template>
  <div class="space-y-4">
    <!-- Business-type filter chips — only shown when >= 2 distinct types exist -->
    <div v-if="visibleChipTypes.length >= 2" class="flex flex-wrap gap-2">
      <button
        type="button"
        class="ui-touch-target ui-press inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-secondary)]"
        :class="activeFilter === null ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
        :aria-pressed="activeFilter === null"
        @click="activeFilter = null"
      >
        {{ t("ownerTemplates.filterAll") }}
      </button>
      <button
        v-for="type in visibleChipTypes"
        :key="type"
        type="button"
        class="ui-touch-target ui-press inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-secondary)]"
        :class="activeFilter === type ? 'border-brand-secondary bg-brand-secondary/10 text-brand-secondary' : 'border-slate-700 text-slate-200 hover:border-brand-secondary'"
        :aria-pressed="activeFilter === type"
        @click="activeFilter = type"
      >
        {{ { restaurant: t("stepPublish.businessTypeRestaurant"), cafe: t("stepPublish.businessTypeCafe"), bakery: t("stepPublish.businessTypeBakery"), grocery: t("stepPublish.businessTypeGrocery"), retail: t("stepPublish.businessTypeRetail"), pharmacy: t("stepPublish.businessTypePharmacy") }[type] ?? type }}
      </button>
    </div>

    <!-- Sample-content checkbox -->
    <label v-if="showSampleToggle" class="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5">
      <span class="text-xs text-slate-300">{{ t("ownerTemplates.withSample") }}</span>
      <input v-model="withSampleContent" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
    </label>

    <!-- Skeleton placeholders while loading -->
    <div v-if="loading" class="grid gap-3 sm:grid-cols-2" aria-busy="true">
      <div v-for="i in 4" :key="i" class="ui-skeleton h-24" />
    </div>

    <!-- Load failure: inline message + retry (A3-36) — the grid must not stay
         silently empty with only a toast. -->
    <div v-else-if="loadError" class="ui-empty-state space-y-2 text-center" role="alert">
      <p class="text-sm font-semibold text-slate-100">{{ t("ownerTemplates.loadFailed") }}</p>
      <button
        type="button"
        class="ui-btn-outline ui-touch-target px-3 py-1.5 text-xs"
        @click="loadTemplates"
      >
        {{ t("common.retry") }}
      </button>
    </div>

    <!-- Template card grid -->
    <div v-else class="grid gap-3 sm:grid-cols-2">
      <button
        v-for="tpl in filteredTemplates"
        :key="tpl.key"
        type="button"
        class="group/card flex items-center gap-3 rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3 text-start transition hover:border-[var(--color-secondary)]/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]/40 disabled:opacity-50"
        :disabled="!!applyingKey"
        @click="applyTemplate(tpl.key)"
      >
        <span class="flex h-12 w-12 shrink-0 overflow-hidden rounded-xl border border-slate-700/60" aria-hidden="true">
          <span class="h-full w-1/2" :style="{ background: tpl.theme.primary_color }" />
          <span class="h-full w-1/2" :style="{ background: tpl.theme.secondary_color }" />
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-slate-100">{{ t("ownerTemplates.kinds." + tpl.key) }}</p>
          <p class="truncate text-[11px] text-slate-500">{{ tpl.categories.join(" · ") }}</p>
          <p class="text-[11px] text-slate-500">{{ t("ownerTemplates.itemCount", { n: tpl.dish_count }) }}</p>
        </div>
        <span v-if="applyingKey === tpl.key" class="shrink-0 text-xs text-slate-400" aria-hidden="true">…</span>
        <AppIcon
          v-else
          name="chevronRight"
          class="h-4 w-4 shrink-0 text-slate-600 transition rtl:scale-x-[-1] group-hover/card:text-[var(--color-secondary)]"
          aria-hidden="true"
        />
      </button>
    </div>
  </div>
</template>

<script setup>
/**
 * TemplateGallery — shared starter-template picker used inline during onboarding
 * (StepStart), and inside a modal from OwnerMenuBuilder and StepTheme. Fetches
 * the available templates from /owner/apply-template/, renders filterable cards,
 * applies the chosen template, and emits "applied" with the server response data.
 */
import { ref, computed, onMounted } from "vue";
import AppIcon from "./AppIcon.vue";
import { useConfirmModal } from "../composables/useConfirmModal";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import { useTenantStore } from "../stores/tenant";
import api from "../lib/api";
import { fetchTemplateSummaries } from "../lib/templateCatalog";

const props = defineProps({
  showSampleToggle: { type: Boolean, default: true },
  initialWithSample: { type: Boolean, default: true },
});

const emit = defineEmits(["applied", "update:applying"]);

const { t } = useI18n();
const { confirm } = useConfirmModal();
const toast = useToastStore();
const tenant = useTenantStore();

const templates = ref([]);
const loading = ref(false);
// A3-36: inline load-error state — a failed catalog fetch must not leave a
// silently empty grid.
const loadError = ref(false);
const applyingKey = ref("");
const withSampleContent = ref(props.initialWithSample);
const activeFilter = ref(null);

// Canonical order for business-type chips
const CHIP_ORDER = ["restaurant", "cafe", "bakery", "grocery", "retail", "pharmacy"];

/** Distinct business_type values present in fetched templates, in canonical order. */
const visibleChipTypes = computed(() => {
  const present = new Set(templates.value.map((t) => t.business_type).filter(Boolean));
  return CHIP_ORDER.filter((type) => present.has(type));
});

/** Templates filtered by the active chip (null = All). */
const filteredTemplates = computed(() => {
  if (activeFilter.value === null) return templates.value;
  return templates.value.filter((tpl) => tpl.business_type === activeFilter.value);
});

const loadTemplates = async () => {
  loading.value = true;
  loadError.value = false;
  try {
    // Cached module-level fetch — the gallery may be remounted on every modal
    // open, but the catalog request only goes out once per page load.
    templates.value = await fetchTemplateSummaries();
  } catch {
    loadError.value = true;
    toast.show(t("ownerTemplates.loadFailed"), "error");
  } finally {
    loading.value = false;
  }
};

onMounted(loadTemplates);

const applyTemplate = async (key) => {
  if (applyingKey.value) return;
  // A3-36: applying overwrites theme + business_type and seeds a sample menu —
  // confirm before the POST, not after.
  const ok = await confirm({
    title: t("ownerTemplates.applyConfirmTitle"),
    body: t("ownerTemplates.applyConfirmBody", { name: t("ownerTemplates.kinds." + key) }),
    confirmLabel: t("ownerTemplates.applyConfirmCta"),
    danger: true,
  });
  if (!ok) return;
  applyingKey.value = key;
  emit("update:applying", true);
  try {
    const { data } = await api.post("/owner/apply-template/", {
      template: key,
      with_sample_content: withSampleContent.value,
    });
    // force: the template just rewrote the theme + business_type, so a still-"fresh"
    // cached meta is stale — bypass the SWR freshness short-circuit.
    await tenant.fetchMeta({ force: true });
    toast.show(
      t("ownerTemplates.applied", { dishes: data.created_dishes, categories: data.created_categories }),
      "success",
    );
    emit("applied", data);
  } catch {
    // A3-36 / C-06: never surface the raw backend detail — translated generic.
    toast.show(t("ownerTemplates.applyFailed"), "error");
  } finally {
    applyingKey.value = "";
    emit("update:applying", false);
  }
};
</script>
