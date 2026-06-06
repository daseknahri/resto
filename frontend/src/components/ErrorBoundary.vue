<template>
  <slot v-if="!hasError" />
  <div
    v-else
    class="flex min-h-screen flex-col items-center justify-center px-4 py-10"
    role="alert"
  >
    <!-- Centered glass card -->
    <div class="ui-glass ui-reveal w-full max-w-md p-8 text-center">
      <!-- Icon -->
      <div aria-hidden="true" class="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl border border-red-500/30 bg-red-500/10">
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="h-8 w-8 text-red-400"
        >
          <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        </svg>
      </div>

      <!-- Message -->
      <div class="space-y-2">
        <p class="ui-kicker mb-1">{{ t("errorBoundary.kicker") }}</p>
        <h2 class="ui-display text-xl font-semibold text-white">{{ t("errorBoundary.title") }}</h2>
        <p class="ui-subtle mx-auto max-w-xs">{{ t("errorBoundary.body") }}</p>
      </div>

      <!-- Actions -->
      <div class="mt-6 flex flex-wrap items-center justify-center gap-3">
        <button
          class="ui-btn-primary ui-press ui-touch-target px-5 text-sm"
          @click="reload"
        >
          {{ t("errorBoundary.reload") }}
        </button>
        <RouterLink
          to="/"
          class="ui-btn-outline ui-touch-target px-5 text-sm"
        >
          {{ t("errorBoundary.goHome") }}
        </RouterLink>
      </div>

      <!-- Dev details (hidden in production) -->
      <details v-if="isDev && errorMessage" class="mt-6 text-start">
        <summary class="cursor-pointer rounded text-xs text-slate-500 transition hover:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/70">
          {{ t("errorBoundary.details") }}
        </summary>
        <pre class="mt-2 overflow-auto rounded-xl border border-red-500/20 bg-slate-950/70 p-3 text-start text-xs text-red-300">{{ errorMessage }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup>
import { onErrorCaptured, ref } from "vue";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();

const hasError = ref(false);
const errorMessage = ref("");
const isDev = import.meta.env.DEV;

onErrorCaptured((err) => {
  hasError.value = true;
  errorMessage.value = err instanceof Error
    ? `${err.name}: ${err.message}\n\n${err.stack || ""}`
    : String(err);
  // Do NOT return false — let Sentry's app.config.errorHandler also receive it.
});

const reload = () => {
  hasError.value = false;
  errorMessage.value = "";
  // Force a full page reload so the component tree is fresh.
  window.location.reload();
};
</script>
