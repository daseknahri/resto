<template>
  <section class="max-w-3xl mx-auto space-y-4 px-4 py-8 text-slate-200">
    <header class="ui-panel p-5 space-y-2 ui-fade-up">
      <p class="ui-kicker">{{ t("contactPage.kicker") }}</p>
      <h1 class="text-3xl font-semibold text-white">{{ t("contactPage.title") }}</h1>
      <p class="text-slate-300">{{ t("contactPage.description") }}</p>
    </header>

    <div class="grid gap-3 sm:grid-cols-3">
      <a href="mailto:support@example.com" class="ui-panel p-4 transition hover:border-[var(--color-secondary)]/70">
        <p class="ui-kicker">{{ t("common.email") }}</p>
        <p class="mt-1 text-sm font-semibold text-slate-100">support@example.com</p>
      </a>
      <a href="https://wa.me/212600000000" target="_blank" rel="noopener noreferrer" class="ui-panel p-4 transition hover:border-[var(--color-secondary)]/70">
        <p class="ui-kicker">{{ t("contactPage.whatsapp") }}</p>
        <p class="mt-1 text-sm font-semibold text-slate-100">+212600000000</p>
      </a>
      <article class="ui-panel p-4">
        <p class="ui-kicker">{{ t("contactPage.hours") }}</p>
        <p class="mt-1 text-sm font-semibold text-slate-100">{{ t("contactPage.hoursValue") }}</p>
      </article>
    </div>

    <article class="ui-panel p-4 space-y-2 text-sm">
      <p class="text-slate-300">{{ t("contactPage.fasterSupport") }}</p>
      <ul class="space-y-1 text-slate-400">
        <li>- {{ t("contactPage.itemTenantSlug") }}</li>
        <li>- {{ t("contactPage.itemAccountEmail") }}</li>
        <li>- {{ t("contactPage.itemIssueSummary") }}</li>
      </ul>
    </article>
  </section>
</template>

<script setup>
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
</script>
