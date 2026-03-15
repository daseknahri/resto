<template>
  <section class="space-y-6 px-4 py-6 md:space-y-8 md:py-10">
    <div class="ui-hero-stage ui-reveal p-5 sm:p-6 md:p-10">
      <div class="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-amber-400/12 blur-3xl"></div>
      <div class="pointer-events-none absolute -left-16 bottom-0 h-64 w-64 rounded-full bg-teal-400/14 blur-3xl"></div>
      <div class="relative space-y-5 text-center">
        <p class="ui-kicker">{{ t("common.demo") }}</p>
        <h1 class="ui-display text-3xl font-semibold text-white sm:text-4xl md:text-5xl">
          {{ t("home.heroTitle") }}
        </h1>
        <p class="mx-auto max-w-2xl text-sm text-slate-300 md:text-base">
          {{ t("home.heroSubtitle") }}
        </p>
        <div class="flex flex-wrap items-center justify-center gap-2">
          <a
            :href="demoMenuUrl"
            class="ui-btn-primary inline-flex items-center gap-2 px-5 py-2.5 text-sm"
            target="_blank"
            rel="noopener noreferrer"
          >
            <AppIcon name="menu" class="h-4 w-4" />
            <span>{{ t("home.viewLiveDemo") }}</span>
          </a>
          <RouterLink to="/get-started" class="ui-btn-outline inline-flex items-center gap-2 px-5 py-2.5 text-sm">
            <AppIcon name="plus" class="h-4 w-4" />
            <span>{{ t("home.getMyMenu") }}</span>
          </RouterLink>
        </div>
      </div>
    </div>

    <div class="grid gap-3 md:grid-cols-3">
      <article class="ui-orbit-card ui-reveal p-4">
        <p class="ui-kicker">{{ t("home.interfaces.landing") }}</p>
        <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.landingTitle") }}</p>
        <p class="mt-1 text-sm text-slate-400">{{ t("home.interfaces.landingText") }}</p>
      </article>
      <article class="ui-orbit-card ui-reveal p-4">
        <p class="ui-kicker">{{ t("home.interfaces.owner") }}</p>
        <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.ownerTitle") }}</p>
        <p class="mt-1 text-sm text-slate-400">{{ t("home.interfaces.ownerText") }}</p>
      </article>
      <article class="ui-orbit-card ui-reveal p-4">
        <p class="ui-kicker">{{ t("home.interfaces.customer") }}</p>
        <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.customerTitle") }}</p>
        <p class="mt-1 text-sm text-slate-400">{{ t("home.interfaces.customerText") }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const demoMenuUrl = import.meta.env.VITE_PUBLIC_DEMO_URL || "https://doro.menu.kepoli.com/menu";
</script>
