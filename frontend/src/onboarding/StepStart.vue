<template>
  <div class="space-y-5">
    <div class="space-y-1">
      <p class="ui-section-kicker">{{ t("ownerTemplates.kicker") }}</p>
      <h2 class="ui-display text-xl font-semibold text-white sm:text-2xl">{{ t("ownerTemplates.title") }}</h2>
      <p class="ui-subtle text-sm">{{ t("ownerTemplates.subtitle") }}</p>
    </div>

    <label class="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2.5">
      <span class="text-xs text-slate-300">{{ t("ownerTemplates.withSample") }}</span>
      <input v-model="withSampleContent" type="checkbox" class="h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-900 text-brand-secondary" />
    </label>

    <div v-if="loading" class="grid gap-3 sm:grid-cols-2" aria-busy="true">
      <div v-for="i in 4" :key="i" class="ui-skeleton h-24" />
    </div>
    <div v-else class="grid gap-3 sm:grid-cols-2">
      <button
        v-for="tpl in templates"
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

    <div class="flex items-center justify-between gap-3 border-t border-slate-800 pt-4">
      <div class="min-w-0">
        <p class="text-sm font-medium text-slate-200">{{ t("ownerTemplates.startScratch") }}</p>
        <p class="text-xs text-slate-500">{{ t("ownerTemplates.startScratchHint") }}</p>
      </div>
      <button
        type="button"
        class="ui-btn-outline ui-press shrink-0 px-4 py-2 text-sm"
        :disabled="!!applyingKey"
        @click="emit('next')"
      >
        {{ t("ownerTemplates.startScratchCta") }}
      </button>
    </div>
  </div>
</template>

<script setup>
/**
 * StepStart — the first onboarding step. The owner picks a starter template
 * (theme + sample menu, applied via /api/owner/apply-template/) or starts from
 * scratch, then continues the wizard. Reuses the ownerTemplates.* i18n.
 */
import { ref, onMounted } from "vue";
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";
import { useToastStore } from "../stores/toast";
import { useTenantStore } from "../stores/tenant";
import api from "../lib/api";

const emit = defineEmits(["next", "back", "publish"]);
const { t } = useI18n();
const toast = useToastStore();
const tenant = useTenantStore();

const templates = ref([]);
const loading = ref(false);
const applyingKey = ref("");
const withSampleContent = ref(true);

onMounted(async () => {
  loading.value = true;
  try {
    const { data } = await api.get("/owner/apply-template/");
    templates.value = Array.isArray(data.templates) ? data.templates : [];
  } catch {
    toast.show(t("ownerTemplates.loadFailed"), "error");
  } finally {
    loading.value = false;
  }
});

const applyTemplate = async (key) => {
  if (applyingKey.value) return;
  applyingKey.value = key;
  try {
    const { data } = await api.post("/owner/apply-template/", {
      template: key,
      with_sample_content: withSampleContent.value,
    });
    await tenant.fetchMeta();
    toast.show(
      t("ownerTemplates.applied", { dishes: data.created_dishes, categories: data.created_categories }),
      "success",
    );
    emit("next");
  } catch (err) {
    toast.show(err?.response?.data?.detail || t("ownerTemplates.applyFailed"), "error");
  } finally {
    applyingKey.value = "";
  }
};
</script>
