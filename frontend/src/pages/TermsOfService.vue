<template>
  <section class="max-w-3xl mx-auto space-y-4 px-4 py-8 text-slate-200">
    <header class="ui-panel p-5 space-y-2">
      <p class="ui-kicker">{{ t("termsOfService.kicker") }}</p>
      <h1 class="text-3xl font-semibold text-white">{{ t("termsOfService.title") }}</h1>
      <p class="text-sm text-slate-400">{{ t("termsOfService.lastUpdated") }}</p>
    </header>
    <div class="ui-panel p-5 space-y-4">
      <p>{{ t("termsOfService.p1") }}</p>
      <p>{{ t("termsOfService.p2") }}</p>
      <p>{{ t("termsOfService.p3") }}</p>
    </div>
  </section>
</template>

<script setup>
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
</script>
