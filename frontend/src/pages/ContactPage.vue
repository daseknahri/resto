<template>
  <section aria-labelledby="contact-page-title" class="mx-auto max-w-4xl space-y-5 px-4 py-6 text-slate-200 md:space-y-6 md:py-8">
    <header class="ui-hero-ribbon ui-reveal overflow-hidden p-0">
      <div class="grid gap-5 p-5 md:grid-cols-[1.15fr,0.85fr] md:p-6">
        <div class="space-y-3">
          <span class="ui-chip-strong w-fit">{{ t("contactPage.kicker") }}</span>
          <div>
            <h1 id="contact-page-title" class="ui-display text-3xl font-semibold text-white md:text-4xl">{{ t("contactPage.title") }}</h1>
            <p class="mt-2 max-w-2xl text-sm leading-7 text-slate-300">{{ t("contactPage.description") }}</p>
          </div>
        </div>
        <div class="grid gap-3 sm:grid-cols-2 md:grid-cols-1">
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("common.email") }}</p>
            <p class="ui-stat-value text-xl">24/7</p>
            <p class="ui-stat-note">{{ t("contactPage.hoursValue") }}</p>
          </div>
          <div class="ui-stat-tile">
            <p class="ui-stat-label">{{ t("contactPage.whatsapp") }}</p>
            <p class="ui-stat-value text-xl">{{ t("contactPage.direct") }}</p>
            <p class="ui-stat-note">{{ t("contactPage.hours") }}</p>
          </div>
        </div>
      </div>
    </header>

    <div class="grid gap-3 sm:grid-cols-3">
      <a
        :href="`mailto:${supportEmail}`"
        class="ui-spotlight-card ui-surface-lift ui-reveal p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]"
        :style="{ '--ui-delay': '0ms' }"
        :aria-label="`${t('common.email')}: ${supportEmail}`"
      >
        <p class="ui-kicker">{{ t("common.email") }}</p>
        <p class="mt-2 truncate text-sm font-semibold text-slate-100">{{ supportEmail }}</p>
      </a>
      <a
        :href="whatsappUrl"
        target="_blank"
        rel="noopener noreferrer"
        class="ui-spotlight-card ui-surface-lift ui-reveal p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-secondary)]"
        :style="{ '--ui-delay': '28ms' }"
        :aria-disabled="whatsappUrl === '#' ? 'true' : undefined"
        :aria-label="whatsappUrl === '#' ? `${t('contactPage.whatsapp')}: ${t('contactPage.notConfigured')}` : `${t('contactPage.whatsapp')}: ${supportPhoneLabel}`"
      >
        <p class="ui-kicker">{{ t("contactPage.whatsapp") }}</p>
        <p class="mt-2 text-sm font-semibold text-slate-100">{{ supportPhoneLabel }}</p>
      </a>
      <div class="ui-spotlight-card ui-reveal p-4" :style="{ '--ui-delay': '56ms' }">
        <h2 class="ui-kicker">{{ t("contactPage.hours") }}</h2>
        <p class="mt-2 text-sm font-semibold text-slate-100">{{ t("contactPage.hoursValue") }}</p>
      </div>
    </div>

    <div class="ui-command-deck ui-reveal p-5 text-sm" :style="{ '--ui-delay': '84ms' }">
      <h2 class="ui-kicker">{{ t("contactPage.fasterSupport") }}</h2>
      <ul class="mt-3 space-y-2 text-slate-300" role="list">
        <li class="flex items-start gap-2">
          <span class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-secondary)] opacity-70" aria-hidden="true"></span>
          <span>{{ t("contactPage.itemTenantSlug") }}</span>
        </li>
        <li class="flex items-start gap-2">
          <span class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-secondary)] opacity-70" aria-hidden="true"></span>
          <span>{{ t("contactPage.itemAccountEmail") }}</span>
        </li>
        <li class="flex items-start gap-2">
          <span class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--color-secondary)] opacity-70" aria-hidden="true"></span>
          <span>{{ t("contactPage.itemIssueSummary") }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { useI18n } from "../composables/useI18n";
import { SUPPORT_EMAIL } from "../lib/brand";
const { t } = useI18n();
const supportEmail = computed(() => (import.meta.env.VITE_CONTACT_EMAIL || SUPPORT_EMAIL).trim());
const supportPhone = computed(() => String(import.meta.env.VITE_CONTACT_PHONE || "").trim());
const supportPhoneLabel = computed(() => supportPhone.value || "+212...");
const whatsappUrl = computed(() => {
  const normalized = supportPhone.value.replace(/[^\d]/g, "");
  const text = encodeURIComponent(import.meta.env.VITE_CONTACT_MESSAGE || "");
  if (!normalized) return "#";
  return `https://wa.me/${normalized}${text ? `?text=${text}` : ""}`;
});
</script>
