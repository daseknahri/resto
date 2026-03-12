<template>
  <section class="mx-auto max-w-4xl space-y-5 px-4 py-6 text-slate-200 md:space-y-6 md:py-8">
    <header class="ui-hero-ribbon ui-fade-up overflow-hidden p-0">
      <div class="grid gap-5 p-5 md:grid-cols-[1.15fr,0.85fr] md:p-6">
        <div class="space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("contactPage.kicker") }}</span>
          <div>
            <h1 class="ui-display text-3xl font-semibold text-white md:text-4xl">{{ t("contactPage.title") }}</h1>
            <p class="mt-2 max-w-2xl text-sm leading-7 text-slate-300">{{ t("contactPage.description") }}</p>
          </div>
        </div>
        <div class="grid gap-3 sm:grid-cols-3 md:grid-cols-1">
          <article class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("common.email") }}</p>
            <p class="ui-stat-value text-xl">24/7</p>
            <p class="ui-stat-note">{{ t("contactPage.hoursValue") }}</p>
          </article>
          <article class="ui-stat-tile">
            <p class="ui-stat-label">WhatsApp</p>
            <p class="ui-stat-value text-xl">Direct</p>
            <p class="ui-stat-note">{{ t("contactPage.whatsapp") }}</p>
          </article>
        </div>
      </div>
    </header>

    <div class="grid gap-3 sm:grid-cols-3">
      <a :href="`mailto:${supportEmail}`" class="ui-spotlight-card p-4 transition hover:border-[var(--color-secondary)]/70">
        <p class="ui-kicker">{{ t("common.email") }}</p>
        <p class="mt-2 text-sm font-semibold text-slate-100">{{ supportEmail }}</p>
      </a>
      <a :href="whatsappUrl" target="_blank" rel="noopener noreferrer" class="ui-spotlight-card p-4 transition hover:border-[var(--color-secondary)]/70">
        <p class="ui-kicker">{{ t("contactPage.whatsapp") }}</p>
        <p class="mt-2 text-sm font-semibold text-slate-100">{{ supportPhoneLabel }}</p>
      </a>
      <article class="ui-spotlight-card p-4">
        <p class="ui-kicker">{{ t("contactPage.hours") }}</p>
        <p class="mt-2 text-sm font-semibold text-slate-100">{{ t("contactPage.hoursValue") }}</p>
      </article>
    </div>

    <article class="ui-command-deck p-5 text-sm">
      <p class="ui-kicker">{{ t("contactPage.fasterSupport") }}</p>
      <ul class="mt-3 space-y-2 text-slate-300">
        <li>- {{ t("contactPage.itemTenantSlug") }}</li>
        <li>- {{ t("contactPage.itemAccountEmail") }}</li>
        <li>- {{ t("contactPage.itemIssueSummary") }}</li>
      </ul>
    </article>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const supportEmail = computed(() => (import.meta.env.VITE_CONTACT_EMAIL || "contact@kepoli.com").trim());
const supportPhone = computed(() => String(import.meta.env.VITE_CONTACT_PHONE || "").trim());
const supportPhoneLabel = computed(() => supportPhone.value || "+212...");
const whatsappUrl = computed(() => {
  const normalized = supportPhone.value.replace(/[^\d]/g, "");
  const text = encodeURIComponent(import.meta.env.VITE_CONTACT_MESSAGE || "");
  if (!normalized) return "#";
  return `https://wa.me/${normalized}${text ? `?text=${text}` : ""}`;
});
</script>
