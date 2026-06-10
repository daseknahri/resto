<template>
  <div class="space-y-5">
    <div class="space-y-1">
      <p class="ui-section-kicker">{{ t("ownerTemplates.kicker") }}</p>
      <h2 class="ui-display text-xl font-semibold text-white sm:text-2xl">{{ t("ownerTemplates.title") }}</h2>
      <p class="ui-subtle text-sm">{{ t("ownerTemplates.subtitle") }}</p>
    </div>

    <TemplateGallery @applied="emit('next')" @update:applying="applying = $event" />

    <div class="flex items-center justify-between gap-3 border-t border-slate-800 pt-4">
      <div class="min-w-0">
        <p class="text-sm font-medium text-slate-200">{{ t("ownerTemplates.startScratch") }}</p>
        <p class="text-xs text-slate-500">{{ t("ownerTemplates.startScratchHint") }}</p>
      </div>
      <button
        type="button"
        class="ui-btn-outline ui-press shrink-0 px-4 py-2 text-sm"
        :disabled="applying"
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
 * or starts from scratch, then continues the wizard. The template gallery lives
 * in components/TemplateGallery.vue and handles fetching, applying, toasts, and
 * tenant meta refresh internally. Reuses the ownerTemplates.* i18n.
 */
import { ref } from "vue";
import { useI18n } from "../composables/useI18n";
import TemplateGallery from "../components/TemplateGallery.vue";

const emit = defineEmits(["next", "back", "publish"]);
const { t } = useI18n();

/** Tracks whether TemplateGallery has an apply POST in flight. */
const applying = ref(false);
</script>
