<template>
  <section aria-labelledby="tos-title" class="ui-page-shell space-y-5 text-slate-200 md:space-y-6 md:py-8">
    <header class="ui-hero-ribbon ui-reveal overflow-hidden p-0">
      <div class="grid gap-4 p-5 md:grid-cols-[minmax(0,1fr),260px] md:p-6">
        <div>
          <p class="ui-kicker">{{ t("termsOfService.kicker") }}</p>
          <h1 id="tos-title" class="ui-display mt-2 text-3xl font-semibold text-white md:text-4xl">
            {{ t("termsOfService.title") }}
          </h1>
          <p class="mt-2 max-w-2xl text-sm text-slate-400">{{ t("termsOfService.lastUpdated") }}</p>
        </div>
        <div class="grid gap-3 sm:grid-cols-3 md:grid-cols-1">
          <div class="ui-admin-subcard">
            <p class="ui-stat-label">01</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("termsOfService.kicker") }}</p>
          </div>
          <div class="ui-admin-subcard">
            <p class="ui-stat-label">02</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("common.terms") }}</p>
          </div>
          <div class="ui-admin-subcard">
            <p class="ui-stat-label">03</p>
            <p class="mt-2 text-sm font-semibold text-white">{{ t("common.contact") }}</p>
          </div>
        </div>
      </div>
    </header>
    <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr),280px]">
      <div class="space-y-4">
        <section
          v-for="(section, index) in sections"
          :key="section"
          class="ui-panel ui-surface-lift ui-reveal p-5 text-sm leading-8 text-slate-300 md:text-base"
          :style="{ '--ui-delay': `${index * 60}ms` }"
        >
          <div class="mb-3 flex items-center justify-between gap-3">
            <h3 class="ui-kicker">{{ String(index + 1).padStart(2, "0") }}</h3>
            <span class="ui-chip" aria-hidden="true">{{ t("common.terms") }}</span>
          </div>
          <p>{{ section }}</p>
        </section>
      </div>
      <aside
        class="ui-panel ui-reveal h-fit space-y-4 p-5 lg:sticky lg:top-24"
        :style="{ '--ui-delay': '180ms' }"
      >
        <div>
          <p class="ui-kicker">{{ t("common.contact") }}</p>
          <p class="mt-2 text-xl font-semibold text-white">{{ t("termsOfService.title") }}</p>
          <a :href="'mailto:' + supportEmail" class="mt-2 block text-sm text-slate-400 underline underline-offset-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2">{{ supportEmail }}</a>
        </div>
        <RouterLink to="/get-started" class="ui-btn-primary w-full justify-center">
          {{ t("common.getStarted") }}
        </RouterLink>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useI18n } from "../composables/useI18n";
import { SUPPORT_EMAIL } from "../lib/brand";

const { t } = useI18n();
const supportEmail = import.meta.env.VITE_CONTACT_EMAIL || SUPPORT_EMAIL;
const sections = computed(() => [t("termsOfService.p1"), t("termsOfService.p2"), t("termsOfService.p3")]);
</script>
