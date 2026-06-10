<template>
  <Teleport to="body">
    <!-- The gallery remounts on each open, but its template fetch is served
         from the module-level cache in lib/templateCatalog — one request per
         page load regardless of how often the modal is reopened. -->
    <Transition name="ui-fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[2100] flex items-end justify-center bg-black/60 px-4 pb-4 backdrop-blur-sm sm:items-center sm:pb-0"
        @click.self="$emit('close')"
        @keydown.esc="$emit('close')"
      >
          <div
            role="dialog"
            aria-modal="true"
            :aria-labelledby="titleId"
            class="ui-panel w-full max-w-lg max-h-[90vh] overflow-y-auto space-y-4 p-5 sm:p-6"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="ui-kicker">{{ t("ownerTemplates.kicker") }}</p>
                <h2 :id="titleId" class="text-base font-bold text-white leading-tight mt-0.5">{{ t("ownerTemplates.title") }}</h2>
                <p class="ui-subtle mt-0.5 text-xs">{{ t("ownerTemplates.subtitle") }}</p>
              </div>
              <button
                class="ui-press ui-touch-target shrink-0 flex items-center justify-center rounded-xl border border-slate-700/60 bg-slate-800/50 text-slate-400 transition hover:border-slate-600 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                :aria-label="t('common.close')"
                @click="$emit('close')"
              >
                <AppIcon name="close" class="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <TemplateGallery @applied="$emit('applied', $event)" />
          </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
// Module-scoped counter: each mounted instance gets a unique dialog title id.
// StepTheme and OwnerMenuBuilder both use this modal, and KeepAlive could keep
// both alive simultaneously — duplicate ids would break aria-labelledby.
let instanceCounter = 0;
</script>

<script setup>
/**
 * TemplatePickerModal — thin modal shell that wraps TemplateGallery for use in
 * OwnerMenuBuilder and StepTheme. Handles Teleport, fade transition, overlay
 * click-away and Escape dismissal, and re-emits the gallery's "applied" event
 * so parent components can react (e.g. remount tabs, advance the wizard step).
 */
import AppIcon from "./AppIcon.vue";
import TemplateGallery from "./TemplateGallery.vue";
import { useI18n } from "../composables/useI18n";

defineProps({
  open: { type: Boolean, required: true },
});

defineEmits(["close", "applied"]);

const { t } = useI18n();

const titleId = `template-picker-modal-title-${++instanceCounter}`;
</script>
