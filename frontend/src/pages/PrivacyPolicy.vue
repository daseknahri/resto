<template>
  <section class="mx-auto max-w-4xl space-y-5 px-4 py-6 text-slate-200 md:space-y-6 md:py-8">
    <header class="ui-hero-ribbon overflow-hidden p-0">
      <div class="p-5 md:p-6">
        <p class="ui-kicker">{{ t("privacyPolicy.kicker") }}</p>
        <h1 class="ui-display mt-2 text-3xl font-semibold text-white md:text-4xl">{{ t("privacyPolicy.title") }}</h1>
        <p class="mt-2 text-sm text-slate-400">{{ t("privacyPolicy.lastUpdated") }}</p>
      </div>
    </header>
    <div class="ui-command-deck space-y-4 p-5 text-sm leading-8 text-slate-300 md:text-base">
      <p>{{ t("privacyPolicy.p1") }}</p>
      <p>{{ t("privacyPolicy.p2") }}</p>
      <p>{{ t("privacyPolicy.p3") }}</p>
    </div>
  </section>
</template>

<script setup>
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
</script>
