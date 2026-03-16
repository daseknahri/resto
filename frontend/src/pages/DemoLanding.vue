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
        <div class="mx-auto flex w-fit items-center gap-2 rounded-full border border-slate-700/80 bg-slate-950/55 px-3 py-1.5 text-xs text-slate-300">
          <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
          <span>doro.menu.kepoli.com</span>
        </div>
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

    <div class="grid gap-4 lg:grid-cols-[0.95fr,1.05fr]">
      <section class="ui-command-deck p-5 md:p-6">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("common.demo") }}</p>
          <h2 class="ui-display text-2xl font-semibold text-white">{{ t("home.interfaces.customerTitle") }}</h2>
          <p class="text-sm text-slate-300">{{ t("home.interfaces.customerText") }}</p>
        </div>

        <div class="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
          <div class="ui-admin-subcard flex items-start gap-3 p-3">
            <span class="ui-chip shrink-0">
              <AppIcon name="home" class="h-3.5 w-3.5" />
            </span>
            <div>
              <p class="text-sm font-semibold text-white">{{ t("home.interfaces.landingTitle") }}</p>
              <p class="mt-1 text-xs text-slate-400">{{ t("home.interfaces.landingText") }}</p>
            </div>
          </div>
          <div class="ui-admin-subcard flex items-start gap-3 p-3">
            <span class="ui-chip shrink-0">
              <AppIcon name="settings" class="h-3.5 w-3.5" />
            </span>
            <div>
              <p class="text-sm font-semibold text-white">{{ t("home.interfaces.ownerTitle") }}</p>
              <p class="mt-1 text-xs text-slate-400">{{ t("home.interfaces.ownerText") }}</p>
            </div>
          </div>
          <div class="ui-admin-subcard flex items-start gap-3 p-3">
            <span class="ui-chip shrink-0">
              <AppIcon name="menu" class="h-3.5 w-3.5" />
            </span>
            <div>
              <p class="text-sm font-semibold text-white">{{ t("home.interfaces.customerTitle") }}</p>
              <p class="mt-1 text-xs text-slate-400">{{ t("home.interfaces.customerText") }}</p>
            </div>
          </div>
        </div>

        <a
          :href="demoMenuUrl"
          class="ui-btn-primary mt-5 inline-flex items-center gap-2 ui-touch-target"
          target="_blank"
          rel="noopener noreferrer"
        >
          <AppIcon name="menu" class="h-4 w-4" />
          <span>{{ t("home.viewLiveDemo") }}</span>
        </a>
      </section>

      <div class="grid gap-3 md:grid-cols-3 lg:grid-cols-1">
      <article class="ui-orbit-card ui-reveal p-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="ui-kicker">{{ t("home.interfaces.landing") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.landingTitle") }}</p>
          </div>
          <AppIcon name="home" class="h-5 w-5 text-amber-300" />
        </div>
        <p class="mt-2 text-sm text-slate-400">{{ t("home.interfaces.landingText") }}</p>
      </article>
      <article class="ui-orbit-card ui-reveal p-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="ui-kicker">{{ t("home.interfaces.owner") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.ownerTitle") }}</p>
          </div>
          <AppIcon name="settings" class="h-5 w-5 text-teal-300" />
        </div>
        <p class="mt-2 text-sm text-slate-400">{{ t("home.interfaces.ownerText") }}</p>
      </article>
      <article class="ui-orbit-card ui-reveal p-4">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="ui-kicker">{{ t("home.interfaces.customer") }}</p>
            <p class="mt-2 text-lg font-semibold text-white">{{ t("home.interfaces.customerTitle") }}</p>
          </div>
          <AppIcon name="menu" class="h-5 w-5 text-sky-300" />
        </div>
        <p class="mt-2 text-sm text-slate-400">{{ t("home.interfaces.customerText") }}</p>
      </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const demoMenuUrl = import.meta.env.VITE_PUBLIC_DEMO_URL || "https://doro.menu.kepoli.com/menu";
</script>
