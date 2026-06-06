<template>
  <section
    class="mx-auto max-w-6xl space-y-6 px-4 py-6 md:space-y-8 md:py-10"
    aria-labelledby="demo-hero-heading"
  >
    <div class="ui-hero-stage ui-reveal p-5 sm:p-6 md:p-10">
      <div class="pointer-events-none absolute end-[-5rem] -top-24 h-64 w-64 rounded-full bg-amber-400/12 blur-3xl" aria-hidden="true"></div>
      <div class="pointer-events-none absolute start-[-4rem] bottom-0 h-64 w-64 rounded-full bg-teal-400/14 blur-3xl" aria-hidden="true"></div>
      <div class="relative space-y-5 text-center">
        <p class="ui-kicker">{{ t("common.demo") }}</p>
        <h1
          id="demo-hero-heading"
          class="ui-display text-3xl font-semibold leading-tight text-white sm:text-4xl md:text-5xl"
        >
          {{ t("home.heroTitle") }}
        </h1>
        <p class="ui-subtle mx-auto max-w-2xl md:text-base">
          {{ t("home.heroSubtitle") }}
        </p>
        <div
          class="mx-auto flex w-fit items-center gap-2 rounded-full border border-slate-700/80 bg-slate-950/55 px-3 py-1.5 text-xs text-slate-300"
          aria-label="Live demo: doro.menu.ibnbatoutaweb.com"
        >
          <span class="ui-live-dot bg-emerald-400" aria-hidden="true"></span>
          <span>doro.menu.ibnbatoutaweb.com</span>
        </div>
        <div class="flex flex-wrap items-center justify-center gap-2">
          <a
            :href="demoMenuUrl"
            class="ui-btn-primary ui-touch-target inline-flex items-center gap-2 px-5 text-sm"
            target="_blank"
            rel="noopener noreferrer"
          >
            <AppIcon name="menu" class="h-4 w-4" aria-hidden="true" />
            <span>{{ t("home.viewLiveDemo") }}</span>
            <span class="sr-only">{{ t("common.opensInNewTab") }}</span>
          </a>
          <RouterLink to="/get-started" class="ui-btn-outline ui-touch-target inline-flex items-center gap-2 px-5 text-sm">
            <AppIcon name="plus" class="h-4 w-4 rtl:scale-x-[-1]" aria-hidden="true" />
            <span>{{ t("home.getMyMenu") }}</span>
          </RouterLink>
        </div>
      </div>
    </div>

    <div class="grid gap-4 lg:grid-cols-[0.95fr,1.05fr]">
      <section class="ui-command-deck ui-reveal p-5 md:p-6" aria-labelledby="demo-interfaces-heading">
        <div class="space-y-2">
          <p class="ui-kicker">{{ t("common.demo") }}</p>
          <h2 id="demo-interfaces-heading" class="ui-display text-2xl font-semibold text-white">{{ t("home.interfaces.customerTitle") }}</h2>
          <p class="ui-subtle">{{ t("home.interfaces.customerText") }}</p>
        </div>

        <a
          :href="demoMenuUrl"
          class="ui-btn-outline ui-touch-target mt-5 inline-flex items-center gap-2 px-5 text-sm"
          target="_blank"
          rel="noopener noreferrer"
        >
          <AppIcon name="menu" class="h-4 w-4" aria-hidden="true" />
          <span>{{ t("home.viewLiveDemo") }}</span>
          <span class="sr-only">{{ t("common.opensInNewTab") }}</span>
        </a>
      </section>

      <ul class="grid gap-3 md:grid-cols-3 lg:grid-cols-1">
        <li
          class="ui-orbit-card ui-reveal p-4"
          :style="{ '--ui-delay': '0ms' }"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0 flex-1">
              <p class="ui-kicker">{{ t("home.interfaces.landing") }}</p>
              <h3 class="mt-2 truncate text-lg font-semibold text-white">{{ t("home.interfaces.landingTitle") }}</h3>
            </div>
            <AppIcon name="home" class="h-5 w-5 shrink-0 text-amber-300" aria-hidden="true" />
          </div>
          <p class="mt-2 text-sm text-slate-400">{{ t("home.interfaces.landingText") }}</p>
        </li>
        <li
          class="ui-orbit-card ui-reveal p-4"
          :style="{ '--ui-delay': '56ms' }"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0 flex-1">
              <p class="ui-kicker">{{ t("home.interfaces.owner") }}</p>
              <h3 class="mt-2 truncate text-lg font-semibold text-white">{{ t("home.interfaces.ownerTitle") }}</h3>
            </div>
            <AppIcon name="settings" class="h-5 w-5 shrink-0 text-teal-300" aria-hidden="true" />
          </div>
          <p class="mt-2 text-sm text-slate-400">{{ t("home.interfaces.ownerText") }}</p>
        </li>
        <li
          class="ui-orbit-card ui-reveal p-4"
          :style="{ '--ui-delay': '112ms' }"
        >
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0 flex-1">
              <p class="ui-kicker">{{ t("home.interfaces.customer") }}</p>
              <h3 class="mt-2 truncate text-lg font-semibold text-white">{{ t("home.interfaces.customerTitle") }}</h3>
            </div>
            <AppIcon name="menu" class="h-5 w-5 shrink-0 text-sky-300" aria-hidden="true" />
          </div>
          <p class="mt-2 text-sm text-slate-400">{{ t("home.interfaces.customerText") }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import AppIcon from "../components/AppIcon.vue";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const demoMenuUrl = import.meta.env.VITE_PUBLIC_DEMO_URL || "https://doro.menu.ibnbatoutaweb.com/menu";
</script>
