<template>
  <section class="mx-auto max-w-6xl space-y-5 px-4 py-6 text-slate-200 md:space-y-6 md:py-8">
    <header class="ui-hero-ribbon overflow-hidden p-0">
      <div class="grid gap-4 p-5 md:grid-cols-[minmax(0,1fr),260px] md:p-6">
        <div>
          <p class="ui-kicker">{{ t("privacyPolicy.kicker") }}</p>
          <h1 class="ui-display mt-2 text-3xl font-semibold text-white md:text-4xl">{{ t("privacyPolicy.title") }}</h1>
          <p class="mt-2 max-w-2xl text-sm text-slate-400">{{ t("privacyPolicy.lastUpdated") }}</p>
        </div>
        <div class="grid gap-3 sm:grid-cols-3 md:grid-cols-1">
          <article class="ui-admin-subcard">
            <p class="ui-stat-label">01</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("privacyPolicy.kicker") }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-stat-label">02</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("common.contact") }}</p>
          </article>
          <article class="ui-admin-subcard">
            <p class="ui-stat-label">03</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("common.privacy") }}</p>
          </article>
        </div>
      </div>
    </header>
    <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr),280px]">
      <div class="space-y-4">
        <article v-for="(section, index) in sections" :key="section" class="ui-command-deck p-5 text-sm leading-8 text-slate-300 md:text-base">
          <div class="mb-3 flex items-center justify-between gap-3">
            <span class="ui-kicker">{{ String(index + 1).padStart(2, "0") }}</span>
            <span class="ui-chip">{{ t("common.privacy") }}</span>
          </div>
          <p>{{ section }}</p>
        </article>
      </div>
      <aside class="ui-workspace-stage h-fit space-y-4 p-5 lg:sticky lg:top-24">
        <div>
          <p class="ui-kicker">{{ t("common.contact") }}</p>
          <p class="mt-2 text-xl font-semibold text-white">{{ t("privacyPolicy.title") }}</p>
          <p class="mt-2 text-sm text-slate-400">{{ supportEmail }}</p>
        </div>
        <RouterLink to="/contact" class="ui-btn-primary w-full justify-center">
          {{ t("common.contact") }}
        </RouterLink>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "../composables/useI18n";

const { t } = useI18n();
const supportEmail = import.meta.env.VITE_CONTACT_EMAIL || "contact@kepoli.com";
const sections = computed(() => [t("privacyPolicy.p1"), t("privacyPolicy.p2"), t("privacyPolicy.p3")]);
</script>
